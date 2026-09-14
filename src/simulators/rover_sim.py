from __future__ import annotations

import asyncio
import logging
import time
from typing import Any

from pymavlink.dialects.v20 import ardupilotmega as mavlink2

from src.core.types import ConnectionEndpoint
from src.simulators.rover_config import (
    RoverHardwareConfig,
    build_default_parameter_list,
)
from src.simulators.rover_physics import RoverKinematics

logger = logging.getLogger(__name__)

DEFAULT_PORT: int = 5770
DEFAULT_SYSTEM_ID: int = 2
DEFAULT_COMPONENT_ID: int = 1
HEARTBEAT_INTERVAL_S: float = 1.0
TELEMETRY_INTERVAL_S: float = 0.1

MAV_TYPE_GROUND_ROVER: int = 10
MAV_AUTOPILOT_GENERIC: int = 0
MAV_STATE_ACTIVE: int = 4
BATTERY_CURRENT_CENTIAMPS: int = 250
BATTERY_PERCENT_DEFAULT: int = 90
GPS_SATELLITES_COUNT: int = 12


class RoverMavlinkServer:
    """MAVLink TCP Server simulating an onboard rover flight controller."""

    def __init__(
        self,
        kinematics: RoverKinematics,
        config: RoverHardwareConfig,
        port: int = DEFAULT_PORT,
        system_id: int = DEFAULT_SYSTEM_ID,
    ) -> None:
        """Initialise MAVLink TCP server for the rover simulator.

        Args:
            kinematics: RoverKinematics instance driving the physics.
            config: Rover hardware configuration.
            port: Local TCP port to bind and listen on.
            system_id: MAVLink system ID for this rover.
        """
        self._kinematics = kinematics
        self._config = config
        self._port = port
        self._system_id = system_id
        self._component_id = DEFAULT_COMPONENT_ID

        self._throttle_pwm: int = config.pwm_center
        self._steering_pwm: int = config.pwm_center
        self._params: list[dict[str, Any]] = build_default_parameter_list(config)

        self._mav = mavlink2.MAVLink(
            None,
            srcSystem=self._system_id,
            srcComponent=self._component_id,
        )
        self._clients: set[asyncio.StreamWriter] = set()
        self._server: asyncio.Server | None = None
        self._tasks: list[asyncio.Task[None]] = []
        self._start_time = time.time()

    @property
    def current_rc(self) -> tuple[int, int]:
        """Current throttle and steering PWM values."""
        return (self._throttle_pwm, self._steering_pwm)

    @property
    def client_count(self) -> int:
        """Number of currently connected MAVLink clients."""
        return len(self._clients)

    @property
    def endpoint(self) -> ConnectionEndpoint:
        """Endpoint descriptor for this simulator."""
        return ConnectionEndpoint(address="127.0.0.1", port=self._port, protocol="tcp")

    def _get_time_boot_ms(self) -> int:
        """Return milliseconds elapsed since simulator start."""
        return int((time.time() - self._start_time) * 1000)

    def _create_heartbeat_bytes(self) -> bytes:
        """Encode a MAVLink HEARTBEAT message as bytes."""
        msg = self._mav.heartbeat_encode(
            type=MAV_TYPE_GROUND_ROVER,
            autopilot=MAV_AUTOPILOT_GENERIC,
            base_mode=0,
            custom_mode=0,
            system_status=MAV_STATE_ACTIVE,
        )
        return bytes(msg.pack(self._mav))

    def _create_attitude_bytes(self) -> bytes:
        """Encode a MAVLink ATTITUDE message as bytes."""
        att = self._kinematics.attitude_data
        msg = self._mav.attitude_encode(
            time_boot_ms=self._get_time_boot_ms(),
            roll=att.roll,
            pitch=att.pitch,
            yaw=att.yaw,
            rollspeed=0.0,
            pitchspeed=0.0,
            yawspeed=self._kinematics.angular_velocity_rps,
        )
        return bytes(msg.pack(self._mav))

    def _create_gps_bytes(self) -> bytes:
        """Encode a MAVLink GPS_RAW_INT message as bytes."""
        gps = self._kinematics.gps_data
        msg = self._mav.gps_raw_int_encode(
            time_usec=int(time.time() * 1e6),
            fix_type=gps.fix_type,
            lat=int(gps.lat * 1e7),
            lon=int(gps.lon * 1e7),
            alt=int(gps.alt * 1000),
            eph=100,
            epv=100,
            vel=int(self._kinematics.speed_mps * 100),
            cog=int(self._kinematics.heading_deg * 100) % 36000,
            satellites_visible=GPS_SATELLITES_COUNT,
        )
        return bytes(msg.pack(self._mav))

    def _create_sys_status_bytes(self) -> bytes:
        """Encode a MAVLink SYS_STATUS message as bytes."""
        voltage_mv = int(self._config.battery_voltage * 1000)
        msg = self._mav.sys_status_encode(
            onboard_control_sensors_present=0,
            onboard_control_sensors_enabled=0,
            onboard_control_sensors_health=0,
            load=100,
            voltage_battery=voltage_mv,
            current_battery=BATTERY_CURRENT_CENTIAMPS,
            battery_remaining=BATTERY_PERCENT_DEFAULT,
            drop_rate_comm=0,
            errors_comm=0,
            errors_count1=0,
            errors_count2=0,
            errors_count3=0,
            errors_count4=0,
        )
        return bytes(msg.pack(self._mav))

    def _create_rc_channels_bytes(self) -> bytes:
        """Encode a MAVLink RC_CHANNELS message as bytes."""
        chans = [self._config.pwm_center] * 18
        chans[0] = self._steering_pwm
        chans[2] = self._throttle_pwm
        msg = self._mav.rc_channels_encode(
            time_boot_ms=self._get_time_boot_ms(),
            chancount=18,
            chan1_raw=chans[0],
            chan2_raw=chans[1],
            chan3_raw=chans[2],
            chan4_raw=chans[3],
            chan5_raw=chans[4],
            chan6_raw=chans[5],
            chan7_raw=chans[6],
            chan8_raw=chans[7],
            chan9_raw=chans[8],
            chan10_raw=chans[9],
            chan11_raw=chans[10],
            chan12_raw=chans[11],
            chan13_raw=chans[12],
            chan14_raw=chans[13],
            chan15_raw=chans[14],
            chan16_raw=chans[15],
            chan17_raw=chans[16],
            chan18_raw=chans[17],
            rssi=255,
        )
        return bytes(msg.pack(self._mav))

    def _create_param_value_bytes(self, param: dict[str, Any]) -> bytes:
        """Encode a single MAVLink PARAM_VALUE message as bytes."""
        msg = self._mav.param_value_encode(
            param_id=param["param_id"].encode("utf-8"),
            param_value=float(param["value"]),
            param_type=int(param["param_type"]),
            param_count=len(self._params),
            param_index=int(param["param_index"]),
        )
        return bytes(msg.pack(self._mav))

    def _handle_rc_override(self, msg: Any) -> None:
        """Update internal PWM values from an RC_CHANNELS_OVERRIDE message."""
        chan1 = getattr(msg, "chan1_raw", 0)
        chan3 = getattr(msg, "chan3_raw", 0)
        if 1000 <= chan1 <= 2000:
            self._steering_pwm = chan1
        if 1000 <= chan3 <= 2000:
            self._throttle_pwm = chan3

    def _handle_param_set(self, msg: Any) -> bytes | None:
        """Update parameter from PARAM_SET and return encoded PARAM_VALUE reply."""
        target_id_raw = getattr(msg, "param_id", "")
        if isinstance(target_id_raw, bytes):
            target_id = target_id_raw.decode("utf-8", errors="ignore").rstrip("\x00")
        else:
            target_id = str(target_id_raw).rstrip("\x00")

        new_val = float(getattr(msg, "param_value", 0.0))
        for p in self._params:
            if p["param_id"] == target_id:
                p["value"] = new_val
                return self._create_param_value_bytes(p)
        return None

    def _handle_param_request_list(self) -> list[bytes]:
        """Generate list of encoded PARAM_VALUE messages for all parameters."""
        return [self._create_param_value_bytes(p) for p in self._params]

    async def _broadcast(self, data: bytes) -> None:
        """Send raw data to all connected clients."""
        for writer in list(self._clients):
            try:
                writer.write(data)
                await writer.drain()
            except (ConnectionError, OSError) as e:
                logger.debug("Failed sending to client, dropping: %s", e)
                self._clients.discard(writer)

    async def _heartbeat_loop(self) -> None:
        """Send HEARTBEAT at 1 Hz."""
        while True:
            await self._broadcast(self._create_heartbeat_bytes())
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)

    async def _telemetry_loop(self) -> None:
        """Send ATTITUDE, GPS_RAW_INT, SYS_STATUS, RC_CHANNELS at 10 Hz."""
        while True:
            if self._clients:
                batch = (
                    self._create_attitude_bytes()
                    + self._create_gps_bytes()
                    + self._create_sys_status_bytes()
                    + self._create_rc_channels_bytes()
                )
                await self._broadcast(batch)
            await asyncio.sleep(TELEMETRY_INTERVAL_S)

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Manage individual TCP client session."""
        self._clients.add(writer)
        client_mav = mavlink2.MAVLink(None)
        logger.info("New MAVLink client connected from %s", writer.get_extra_info("peername"))
        try:
            while True:
                data = await reader.read(1024)
                if not data:
                    break
                msgs = client_mav.parse_buffer(data)
                if not msgs:
                    continue
                await self._dispatch_incoming_messages(msgs, writer)
        except (ConnectionError, OSError) as e:
            logger.debug("Client session terminated: %s", e)
        finally:
            self._clients.discard(writer)
            writer.close()
            await writer.wait_closed()

    async def _dispatch_incoming_messages(
        self,
        msgs: list[Any],
        writer: asyncio.StreamWriter,
    ) -> None:
        """Dispatch parsed incoming MAVLink messages."""
        for msg in msgs:
            msg_type = msg.get_type()
            if msg_type == "RC_CHANNELS_OVERRIDE":
                self._handle_rc_override(msg)
            elif msg_type == "PARAM_REQUEST_LIST":
                for frame in self._handle_param_request_list():
                    writer.write(frame)
                await writer.drain()
            elif msg_type == "PARAM_SET":
                reply = self._handle_param_set(msg)
                if reply:
                    writer.write(reply)
                    await writer.drain()

    async def start(self) -> None:
        """Start the TCP server and background broadcast tasks."""
        self._server = await asyncio.start_server(self._handle_client, "0.0.0.0", self._port)
        logger.info("MAVLink server listening on 0.0.0.0:%d", self._port)
        self._tasks.append(asyncio.create_task(self._heartbeat_loop()))
        self._tasks.append(asyncio.create_task(self._telemetry_loop()))

    async def stop(self) -> None:
        """Stop server, cancel tasks, and close client connections."""
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
        if self._server:
            self._server.close()
            await self._server.wait_closed()
        for writer in list(self._clients):
            try:
                writer.close()
                await writer.wait_closed()
            except (ConnectionError, OSError, RuntimeError):
                pass
        self._clients.clear()
        logger.info("MAVLink server stopped")

