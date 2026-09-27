from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from src.core.connection import ConnectionManager, MavlinkConnection
from src.core.parameter_store import ParameterStore
from src.core.protocol import (
    create_arm_disarm_msg,
    create_param_request_list_msg,
    create_param_set_msg,
    create_rc_override_msg,
    create_set_mode_msg,
    parse_attitude,
    parse_battery,
    parse_global_position,
    parse_gps,
    parse_heartbeat,
    parse_param_value,
    parse_rc_channels,
    parse_vehicle_status,
    parse_vfr_hud,
)
from src.core.telemetry_bus import TelemetryBus
from src.core.telemetry_streams import TelemetryStreams
from src.core.types import ConnectionEndpoint, ConnectionState, VehicleIdentity
from src.core.vehicle_registry import VehicleRegistry

logger = logging.getLogger(__name__)

DEFAULT_SCAN_TIMEOUT_S: float = 5.0
COMMAND_ACK_TIMEOUT_S: float = 3.0
MAV_RESULT_ACCEPTED: int = 0
MAV_RESULT_IN_PROGRESS: int = 5


class AutoConfigEngine:
    """Coordinates vehicle discovery, automatic parameter sync, and telemetry ingestion."""

    def __init__(
        self,
        conn_mgr: ConnectionManager,
        registry: VehicleRegistry,
        param_store: ParameterStore,
        bus: TelemetryBus,
    ) -> None:
        """Initialise AutoConfigEngine with system subsystems.

        Args:
            conn_mgr: ConnectionManager managing active MAVLink endpoints.
            registry: VehicleRegistry tracking active vehicles.
            param_store: ParameterStore caching vehicle configuration.
            bus: TelemetryBus distributing system and telemetry events.
        """
        self._conn_mgr = conn_mgr
        self._registry = registry
        self._param_store = param_store
        self._bus = bus
        self._discovered_identities: dict[tuple[str, int], VehicleIdentity] = {}
        self._watched_connections: set[MavlinkConnection] = set()
        self._streams = TelemetryStreams()
        self._parameter_tasks: set[asyncio.Task[None]] = set()
        self._command_waiters: dict[
            tuple[MavlinkConnection, int, int, int], asyncio.Future[int]
        ] = {}

    async def _handle_incoming_msg(
        self,
        conn: MavlinkConnection,
        msg: Any,
    ) -> None:
        """Process and decode incoming MAVLink message from a connection."""
        msg_type = getattr(msg, "get_type", lambda: "")()
        sys_id = getattr(msg, "get_srcSystem", lambda: 0)()
        comp_id = getattr(msg, "get_srcComponent", lambda: 0)()

        if msg_type == "HEARTBEAT":
            await self._process_heartbeat(conn, msg, sys_id, comp_id)
        elif msg_type == "COMMAND_ACK":
            self._streams.handle_ack(conn, msg)
            self._handle_command_ack(conn, msg, sys_id)
        elif msg_type == "PARAM_VALUE":
            await self._process_param_value(sys_id, msg)
        elif msg_type == "ATTITUDE":
            await self._process_attitude(sys_id, msg)
        elif msg_type == "GPS_RAW_INT":
            await self._process_gps(sys_id, msg)
        elif msg_type in ("GLOBAL_POSITION_INT", "VFR_HUD"):
            await self._process_motion(sys_id, msg)
        elif msg_type in ("SYS_STATUS", "BATTERY_STATUS"):
            await self._process_battery(sys_id, msg)
        elif msg_type == "RC_CHANNELS":
            await self._process_rc(sys_id, msg)

    async def _process_heartbeat(
        self,
        conn: MavlinkConnection,
        msg: Any,
        sys_id: int,
        comp_id: int,
    ) -> None:
        """Handle HEARTBEAT by registering vehicle and querying parameters."""
        try:
            identity = parse_heartbeat(msg, sys_id, comp_id)
            key = (conn.endpoint.address, conn.endpoint.port)
            is_new = not self._registry.is_registered(identity.system_id)
            self._discovered_identities[key] = identity
            await self._registry.register(identity)
            try:
                status = parse_vehicle_status(msg, identity.system_id)
            except ValueError:
                status = None
            if status is not None:
                await self._bus.publish("vehicle.status", status)
            stream_task = self._streams.start(conn, identity)

            if is_new:
                if stream_task is None:
                    await self._request_parameters(conn, identity, None)
                else:
                    task = asyncio.create_task(
                        self._request_parameters(conn, identity, stream_task),
                    )
                    self._parameter_tasks.add(task)
                    task.add_done_callback(self._parameter_tasks.discard)
        except (ValueError, KeyError) as e:
            logger.error("Failed to parse heartbeat: %s", e)

    async def _request_parameters(
        self, conn: MavlinkConnection, identity: VehicleIdentity,
        stream_task: asyncio.Task[None] | None,
    ) -> None:
        """Keep the initial parameter burst behind telemetry interval acknowledgments."""
        try:
            if stream_task is not None:
                await stream_task
            logger.info("AutoConfig requesting parameters for vehicle %d", identity.system_id)
            await conn.send_message(create_param_request_list_msg(
                identity.system_id, identity.component_id,
            ))
        except (ConnectionError, OSError) as exc:
            logger.error("Parameter request failed for system %d: %s", identity.system_id, exc)

    async def _on_connection_state(
        self, conn: MavlinkConnection, state: ConnectionState,
    ) -> None:
        if state not in (ConnectionState.DISCONNECTED, ConnectionState.HEARTBEAT_LOST):
            return
        key = (conn.endpoint.address, conn.endpoint.port)
        identity = self._discovered_identities.pop(key, None)
        if identity is None:
            return
        if any(v.system_id == identity.system_id for v in self._discovered_identities.values()):
            return
        self._param_store.clear(identity.system_id)
        if self._registry.is_registered(identity.system_id):
            await self._registry.unregister(identity.system_id)

    def _handle_command_ack(self, conn: MavlinkConnection, msg: Any, sys_id: int) -> None:
        """Complete the matching arm or mode request from this connection."""
        if msg.result == MAV_RESULT_IN_PROGRESS:
            return
        pending = self._command_waiters.get((
            conn, sys_id, int(msg.get_srcComponent()), int(msg.command),
        ))
        if pending is not None and not pending.done():
            pending.set_result(int(msg.result))

    def _connection_for_system(self, system_id: int) -> MavlinkConnection:
        """Find the live endpoint that discovered a vehicle."""
        for conn in self._conn_mgr.list_connections():
            key = (conn.endpoint.address, conn.endpoint.port)
            identity = self._discovered_identities.get(key)
            if identity is not None and identity.system_id == system_id:
                if conn.state == ConnectionState.CONNECTED:
                    return conn
                break
        raise ConnectionError(f"Vehicle {system_id} has no connected MAVLink endpoint")

    async def _send_confirmed_command(self, system_id: int, msg: Any) -> None:
        """Transmit to the discovered endpoint and require an accepted COMMAND_ACK."""
        conn = self._connection_for_system(system_id)
        command = int(msg.command)
        key = (conn, system_id, int(msg.target_component), command)
        if key in self._command_waiters:
            raise ValueError(f"Command {command} already pending for vehicle {system_id}")
        future: asyncio.Future[int] = asyncio.get_running_loop().create_future()
        self._command_waiters[key] = future
        try:
            await conn.send_message(msg)
            result = await asyncio.wait_for(future, COMMAND_ACK_TIMEOUT_S)
            if result != MAV_RESULT_ACCEPTED:
                raise ValueError(f"Vehicle {system_id} rejected command {command}: result {result}")
        except asyncio.TimeoutError as exc:
            raise TimeoutError(
                f"Vehicle {system_id} did not acknowledge command {command}"
            ) from exc
        finally:
            self._command_waiters.pop(key, None)

    async def _process_param_value(self, sys_id: int, msg: Any) -> None:
        """Handle PARAM_VALUE by updating parameter store."""
        try:
            param = parse_param_value(msg)
            await self._param_store.upsert(sys_id, param)
        except ValueError as e:
            logger.debug("Failed parsing PARAM_VALUE: %s", e)

    async def _process_attitude(self, sys_id: int, msg: Any) -> None:
        """Handle ATTITUDE message and publish to telemetry bus."""
        try:
            att = parse_attitude(msg)
            await self._bus.publish("telemetry.attitude", {"system_id": sys_id, **att.to_dict()})
        except ValueError as e:
            logger.warning("Failed parsing ATTITUDE for system %d: %s", sys_id, e)

    async def _process_gps(self, sys_id: int, msg: Any) -> None:
        """Handle GPS_RAW_INT message and publish to telemetry bus."""
        try:
            gps = parse_gps(msg)
            await self._bus.publish("telemetry.gps", {"system_id": sys_id, **gps.to_dict()})
        except ValueError as e:
            logger.warning("Failed parsing GPS_RAW_INT for system %d: %s", sys_id, e)

    async def _process_battery(self, sys_id: int, msg: Any) -> None:
        """Handle battery status message and publish to telemetry bus."""
        try:
            batt = parse_battery(msg)
            await self._bus.publish("telemetry.battery", {"system_id": sys_id, **batt.to_dict()})
        except ValueError as e:
            logger.warning("Failed parsing %s for system %d: %s", msg.get_type(), sys_id, e)

    async def _process_rc(self, sys_id: int, msg: Any) -> None:
        """Handle RC_CHANNELS message and publish to telemetry bus."""
        try:
            rc = parse_rc_channels(msg)
            await self._bus.publish("telemetry.rc", {"system_id": sys_id, "channels": rc})
        except ValueError as e:
            logger.debug("Failed parsing RC: %s", e)

    async def _process_motion(self, sys_id: int, msg: Any) -> None:
        """Publish fused position and HUD speed without losing GPS fix metadata."""
        kind = msg.get_type()
        try:
            if kind == "GLOBAL_POSITION_INT":
                data, event = parse_global_position(msg), "telemetry.position"
            else:
                data, event = parse_vfr_hud(msg), "telemetry.hud"
            await self._bus.publish(event, {"system_id": sys_id, **data})
        except ValueError as exc:
            logger.warning("Failed parsing %s for system %d: %s", kind, sys_id, exc)

    async def run_scan(
        self,
        endpoint: ConnectionEndpoint,
        timeout_s: float = DEFAULT_SCAN_TIMEOUT_S,
    ) -> VehicleIdentity | None:
        """Scan a single endpoint for a connected vehicle.

        Args:
            endpoint: Target ConnectionEndpoint.
            timeout_s: Maximum seconds to await heartbeat.

        Returns:
            Discovered VehicleIdentity, or None if timed out.
        """
        conn = await self._conn_mgr.add_connection(endpoint)

        async def msg_handler(msg: Any) -> None:
            await self._handle_incoming_msg(conn, msg)

        if conn not in self._watched_connections:
            conn.on_message(msg_handler)
            async def state_handler(state: ConnectionState) -> None:
                await self._on_connection_state(conn, state)
            conn.on_state_change(state_handler)
            self._watched_connections.add(conn)

        start_time = time.time()
        key = (endpoint.address, endpoint.port)
        while time.time() - start_time < timeout_s:
            if key in self._discovered_identities:
                return self._discovered_identities[key]
            await asyncio.sleep(0.1)
        return None

    async def run_full_scan(
        self,
        endpoints: list[ConnectionEndpoint],
        timeout_s: float = DEFAULT_SCAN_TIMEOUT_S,
    ) -> list[VehicleIdentity]:
        """Scan multiple endpoints concurrently.

        Args:
            endpoints: List of ConnectionEndpoints to scan.
            timeout_s: Scan timeout in seconds.

        Returns:
            List of discovered VehicleIdentity objects.
        """
        tasks = [self.run_scan(ep, timeout_s=timeout_s) for ep in endpoints]
        results = await asyncio.gather(*tasks)
        return [identity for identity in results if identity is not None]

    async def send_rc_override(
        self,
        system_id: int,
        throttle_pwm: int,
        steering_pwm: int = 1500,
        pitch_pwm: int = 0,
        yaw_pwm: int = 0,
    ) -> None:
        """Send RC override commands to control vehicle actuators.

        Args:
            system_id: Target vehicle system ID.
            throttle_pwm: Throttle PWM value (1000-2000).
            steering_pwm: Steering or roll PWM value (1000-2000).
            pitch_pwm: Pitch PWM value (1000-2000, or 0 for unassigned).
            yaw_pwm: Yaw PWM value (1000-2000, or 0 for unassigned).
        """
        msg = create_rc_override_msg(
            system_id,
            1,
            throttle=throttle_pwm,
            steering=steering_pwm,
            pitch=pitch_pwm,
            yaw=yaw_pwm,
        )
        await self._connection_for_system(system_id).send_message(msg)

    async def set_parameter(
        self,
        system_id: int,
        param_id: str,
        value: float,
    ) -> None:
        """Transmit a parameter update to the vehicle.

        Args:
            system_id: Target vehicle system ID.
            param_id: Parameter name to update.
            value: New float parameter value.
        """
        msg = create_param_set_msg(system_id, 1, param_id, value)
        await self._connection_for_system(system_id).send_message(msg)

    async def arm_vehicle(self, system_id: int, arm: bool) -> None:
        """Transmit arm or disarm command to vehicle.

        Args:
            system_id: Target vehicle system ID.
            arm: True to arm vehicle motors, False to disarm.
        """
        msg = create_arm_disarm_msg(system_id, 1, arm)
        await self._send_confirmed_command(system_id, msg)

    async def set_mode(self, system_id: int, mode: str | int) -> None:
        """Transmit flight mode change command to vehicle.

        Args:
            system_id: Target vehicle system ID.
            mode: Flight mode name or numeric mode identifier.
        """
        msg = create_set_mode_msg(system_id, 1, mode)
        await self._send_confirmed_command(system_id, msg)

