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
    parse_gps,
    parse_heartbeat,
    parse_param_value,
    parse_rc_channels,
)
from src.core.telemetry_bus import TelemetryBus
from src.core.types import ConnectionEndpoint, VehicleIdentity
from src.core.vehicle_registry import VehicleRegistry

logger = logging.getLogger(__name__)

DEFAULT_SCAN_TIMEOUT_S: float = 5.0


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
        elif msg_type == "PARAM_VALUE":
            await self._process_param_value(sys_id, msg)
        elif msg_type == "ATTITUDE":
            await self._process_attitude(sys_id, msg)
        elif msg_type == "GPS_RAW_INT":
            await self._process_gps(sys_id, msg)
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

            if is_new:
                logger.info("AutoConfig requesting parameters for vehicle %d", identity.system_id)
                param_req = create_param_request_list_msg(identity.system_id, identity.component_id)
                await conn.send_message(param_req)
        except (ValueError, KeyError) as e:
            logger.error("Failed to parse heartbeat: %s", e)

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
            logger.debug("Failed parsing ATTITUDE: %s", e)

    async def _process_gps(self, sys_id: int, msg: Any) -> None:
        """Handle GPS_RAW_INT message and publish to telemetry bus."""
        try:
            gps = parse_gps(msg)
            await self._bus.publish("telemetry.gps", {"system_id": sys_id, **gps.to_dict()})
        except ValueError as e:
            logger.debug("Failed parsing GPS: %s", e)

    async def _process_battery(self, sys_id: int, msg: Any) -> None:
        """Handle battery status message and publish to telemetry bus."""
        try:
            batt = parse_battery(msg)
            await self._bus.publish("telemetry.battery", {"system_id": sys_id, **batt.to_dict()})
        except ValueError as e:
            logger.debug("Failed parsing battery: %s", e)

    async def _process_rc(self, sys_id: int, msg: Any) -> None:
        """Handle RC_CHANNELS message and publish to telemetry bus."""
        try:
            rc = parse_rc_channels(msg)
            await self._bus.publish("telemetry.rc", {"system_id": sys_id, "channels": rc})
        except ValueError as e:
            logger.debug("Failed parsing RC: %s", e)

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

        conn.on_message(msg_handler)

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
        for conn in self._conn_mgr.list_connections():
            await conn.send_message(msg)

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
        for conn in self._conn_mgr.list_connections():
            await conn.send_message(msg)

    async def arm_vehicle(self, system_id: int, arm: bool) -> None:
        """Transmit arm or disarm command to vehicle.

        Args:
            system_id: Target vehicle system ID.
            arm: True to arm vehicle motors, False to disarm.
        """
        msg = create_arm_disarm_msg(system_id, 1, arm)
        for conn in self._conn_mgr.list_connections():
            await conn.send_message(msg)

    async def set_mode(self, system_id: int, mode: str | int) -> None:
        """Transmit flight mode change command to vehicle.

        Args:
            system_id: Target vehicle system ID.
            mode: Flight mode name or numeric mode identifier.
        """
        msg = create_set_mode_msg(system_id, 1, mode)
        for conn in self._conn_mgr.list_connections():
            await conn.send_message(msg)

