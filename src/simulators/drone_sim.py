from __future__ import annotations

import asyncio
import logging
import math
import time
from typing import Any

from src.core.protocol import (
    COPTER_FLIGHT_MODES,
    MAV_CMD_COMPONENT_ARM_DISARM,
    MAV_CMD_DO_SET_MODE,
    MAV_MODE_FLAG_SAFETY_ARMED,
    get_simulator_mavlink_dialect,
)
from src.core.types import ConnectionEndpoint
from src.simulators.drone_config import (
    DroneHardwareConfig,
    build_default_drone_parameters,
)
from src.simulators.drone_physics import DroneKinematics

mavlink2 = get_simulator_mavlink_dialect()
logger = logging.getLogger(__name__)

DEFAULT_PORT: int = 5771
DEFAULT_SYSTEM_ID: int = 3
DEFAULT_COMPONENT_ID: int = 1
HEARTBEAT_INTERVAL_S: float = 1.0
TELEMETRY_INTERVAL_S: float = 0.1
PHYSICS_INTERVAL_S: float = 0.05

MAV_TYPE_QUADROTOR: int = 2
MAV_AUTOPILOT_ARDUPILOTMEGA: int = 3
MAV_STATE_ACTIVE: int = 4
BATTERY_CURRENT_CENTIAMPS: int = 450
BATTERY_PERCENT_DEFAULT: int = 95
GPS_SATELLITES_COUNT: int = 14
MAV_RESULT_ACCEPTED: int = 0
MAV_RESULT_DENIED: int = 2
MAV_RESULT_UNSUPPORTED: int = 3


class DroneMavlinkServer:
    """MAVLink TCP Server simulating an ArduPilot Copter flight controller."""

    def __init__(
        self,
        kinematics: DroneKinematics,
        config: DroneHardwareConfig,
        port: int = DEFAULT_PORT,
        system_id: int = DEFAULT_SYSTEM_ID,
    ) -> None:
        """Initialise MAVLink TCP server for the drone simulator."""
        self._kinematics = kinematics
        self._config = config
        self._port = port
        self._system_id = system_id
        self._component_id = DEFAULT_COMPONENT_ID
        self._armed = False
        self._flight_mode = COPTER_FLIGHT_MODES["STABILIZE"]

        self._roll_pwm: int = config.pwm_center
        self._pitch_pwm: int = config.pwm_center
        self._throttle_pwm: int = config.pwm_center
        self._yaw_pwm: int = config.pwm_center
        self._params: list[dict[str, Any]] = build_default_drone_parameters(config)

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
    def current_rc(self) -> tuple[int, int, int, int]:
        """Current 4-axis PWM values (roll, pitch, throttle, yaw)."""
        return (self._roll_pwm, self._pitch_pwm, self._throttle_pwm, self._yaw_pwm)

    @property
    def client_count(self) -> int:
        """Number of active MAVLink client connections."""
        return len(self._clients)

    @property
    def endpoint(self) -> ConnectionEndpoint:
        """ConnectionEndpoint descriptor for this simulator."""
        return ConnectionEndpoint(address="127.0.0.1", port=self._port, protocol="tcp")

    def _get_time_boot_ms(self) -> int:
        """Return milliseconds elapsed since simulator boot."""
        return int((time.time() - self._start_time) * 1000)

    def _create_heartbeat_bytes(self) -> bytes:
        """Encode ArduPilot Copter MAVLink HEARTBEAT message."""
        msg = self._mav.heartbeat_encode(
            type=MAV_TYPE_QUADROTOR,
            autopilot=MAV_AUTOPILOT_ARDUPILOTMEGA,
            base_mode=MAV_MODE_FLAG_SAFETY_ARMED if self._armed else 0,
            custom_mode=self._flight_mode,
            system_status=MAV_STATE_ACTIVE,
        )
        return bytes(msg.pack(self._mav))

    def _create_attitude_bytes(self) -> bytes:
        """Encode MAVLink ATTITUDE telemetry message."""
        att = self._kinematics.attitude_data
        msg = self._mav.attitude_encode(
            time_boot_ms=self._get_time_boot_ms(),
            roll=att.roll,
            pitch=att.pitch,
            yaw=att.yaw,
            rollspeed=0.0,
            pitchspeed=0.0,
            yawspeed=0.0,
        )
        return bytes(msg.pack(self._mav))

    def _create_gps_bytes(self) -> bytes:
        """Encode MAVLink GPS_RAW_INT message with altitude."""
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
            cog=int(math.degrees(self._kinematics.attitude_data.yaw) * 100) % 36000,
            satellites_visible=GPS_SATELLITES_COUNT,
        )
        return bytes(msg.pack(self._mav))

    def _create_sys_status_bytes(self) -> bytes:
        """Encode MAVLink SYS_STATUS message."""
        voltage_mv = int(self._config.battery_voltage * 1000)
        msg = self._mav.sys_status_encode(
            onboard_control_sensors_present=0,
            onboard_control_sensors_enabled=0,
            onboard_control_sensors_health=0,
            load=150,
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
        """Encode MAVLink RC_CHANNELS message."""
        chans = [self._config.pwm_center] * 18
        chans[0] = self._roll_pwm
        chans[1] = self._pitch_pwm
        chans[2] = self._throttle_pwm
        chans[3] = self._yaw_pwm
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
        """Encode single PARAM_VALUE message."""
        msg = self._mav.param_value_encode(
            param_id=param["param_id"].encode("utf-8"),
            param_value=float(param["value"]),
            param_type=int(param["param_type"]),
            param_count=len(self._params),
            param_index=int(param["param_index"]),
        )
        return bytes(msg.pack(self._mav))

    def _handle_rc_override(self, msg: Any) -> None:
        """Update 4-axis PWM setpoints from RC_CHANNELS_OVERRIDE."""
        c1 = getattr(msg, "chan1_raw", 0)
        c2 = getattr(msg, "chan2_raw", 0)
        c3 = getattr(msg, "chan3_raw", 0)
        c4 = getattr(msg, "chan4_raw", 0)
        if 1000 <= c1 <= 2000:
            self._roll_pwm = c1
        if 1000 <= c2 <= 2000:
            self._pitch_pwm = c2
        if 1000 <= c3 <= 2000:
            self._throttle_pwm = c3
        if 1000 <= c4 <= 2000:
            self._yaw_pwm = c4

    def _handle_param_set(self, msg: Any) -> bytes | None:
        """Update parameter value and return encoded response."""
        raw_id = getattr(msg, "param_id", "")
        if isinstance(raw_id, bytes):
            p_id = raw_id.decode("utf-8", "ignore").rstrip("\x00")
        else:
            p_id = str(raw_id).rstrip("\x00")
        val = float(getattr(msg, "param_value", 0.0))
        for p in self._params:
            if p["param_id"] == p_id:
                p["value"] = val
                return self._create_param_value_bytes(p)
        return None

    def _handle_param_request_list(self) -> list[bytes]:
        """Generate encoded PARAM_VALUE frames for all parameters."""
        return [self._create_param_value_bytes(p) for p in self._params]

    def _handle_command_long(self, msg: Any) -> bytes:
        """Apply supported mock flight commands and acknowledge the result."""
        command = int(msg.command)
        result = MAV_RESULT_UNSUPPORTED
        if command == MAV_CMD_COMPONENT_ARM_DISARM:
            arm_value = float(msg.param1)
            if arm_value in (0.0, 1.0):
                self._armed = arm_value == 1.0
                result = MAV_RESULT_ACCEPTED
            else:
                result = MAV_RESULT_DENIED
        elif command == MAV_CMD_DO_SET_MODE:
            mode_value = float(msg.param2)
            if mode_value.is_integer() and int(mode_value) in COPTER_FLIGHT_MODES.values():
                self._flight_mode = int(mode_value)
                result = MAV_RESULT_ACCEPTED
            else:
                result = MAV_RESULT_DENIED
        ack = self._mav.command_ack_encode(command, result)
        return bytes(ack.pack(self._mav))

    async def _broadcast(self, data: bytes) -> None:
        """Broadcast byte buffer to active TCP client connections."""
        for writer in list(self._clients):
            try:
                writer.write(data)
                await writer.drain()
            except (ConnectionError, OSError) as e:
                logger.debug("Client write failed: %s", e)
                self._clients.discard(writer)

    async def _heartbeat_loop(self) -> None:
        """Transmit HEARTBEAT frame at 1 Hz."""
        while True:
            await self._broadcast(self._create_heartbeat_bytes())
            await asyncio.sleep(HEARTBEAT_INTERVAL_S)

    async def _telemetry_loop(self) -> None:
        """Transmit telemetry burst at 10 Hz."""
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

    async def _physics_loop(self) -> None:
        """Run physics simulation updates at 20 Hz."""
        last_t = time.time()
        while True:
            await asyncio.sleep(PHYSICS_INTERVAL_S)
            now = time.time()
            dt = now - last_t
            last_t = now
            self._kinematics.update(
                self._throttle_pwm,
                self._roll_pwm,
                self._pitch_pwm,
                self._yaw_pwm,
                dt,
            )

    async def _handle_client(
        self,
        reader: asyncio.StreamReader,
        writer: asyncio.StreamWriter,
    ) -> None:
        """Manage TCP client session."""
        self._clients.add(writer)
        client_mav = mavlink2.MAVLink(None)
        logger.info("New drone MAVLink client connected from %s", writer.get_extra_info("peername"))
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
            logger.debug("Drone client session ended: %s", e)
        finally:
            self._clients.discard(writer)
            writer.close()
            await writer.wait_closed()

    async def _dispatch_incoming_messages(
        self,
        msgs: list[Any],
        writer: asyncio.StreamWriter,
    ) -> None:
        """Process incoming MAVLink frames."""
        for msg in msgs:
            mtype = msg.get_type()
            if mtype == "RC_CHANNELS_OVERRIDE":
                self._handle_rc_override(msg)
            elif mtype == "PARAM_REQUEST_LIST":
                for frame in self._handle_param_request_list():
                    writer.write(frame)
                await writer.drain()
            elif mtype == "PARAM_SET":
                reply = self._handle_param_set(msg)
                if reply:
                    writer.write(reply)
                    await writer.drain()
            elif mtype == "COMMAND_LONG":
                writer.write(self._handle_command_long(msg))
                await writer.drain()

    async def start(self) -> None:
        """Start drone TCP server and background tasks."""
        self._server = await asyncio.start_server(self._handle_client, "0.0.0.0", self._port)
        logger.info("Drone MAVLink server listening on 0.0.0.0:%d", self._port)
        self._tasks.append(asyncio.create_task(self._heartbeat_loop()))
        self._tasks.append(asyncio.create_task(self._telemetry_loop()))
        self._tasks.append(asyncio.create_task(self._physics_loop()))

    async def stop(self) -> None:
        """Cancel tasks and close server."""
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
            except (ConnectionError, OSError, RuntimeError) as e:
                logger.debug("Writer cleanup during stop: %s", e)
        self._clients.clear()
        logger.info("Drone MAVLink server stopped")
