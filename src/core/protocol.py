from __future__ import annotations

import logging
import math
from typing import Any

from pymavlink import mavutil
from pymavlink.dialects.v20 import ardupilotmega as mavlink2

from src.core.types import (
    AttitudeData,
    AutopilotType,
    BatteryData,
    ConnectionEndpoint,
    GpsData,
    Parameter,
    VehicleIdentity,
    VehicleType,
)

logger = logging.getLogger(__name__)

GPS_COORD_SCALE: float = 1e7
GPS_ALT_SCALE_M: float = 1000.0
BATT_VOLT_SCALE: float = 1000.0
BATT_AMP_SCALE: float = 100.0
NUM_RC_CHANNELS: int = 18
MAV_CMD_SET_MESSAGE_INTERVAL: int = 511
MICROSECONDS_PER_SECOND: int = 1_000_000
VELOCITY_CM_PER_M: float = 100.0
UNKNOWN_BATTERY_VOLTAGE: int = 65535


def get_simulator_mavlink_dialect() -> Any:
    """Expose the MAVLink v2 dialect for simulator message synthesis."""
    return mavlink2

MAV_CMD_COMPONENT_ARM_DISARM: int = 400
MAV_CMD_DO_SET_MODE: int = 176
MAV_MODE_FLAG_CUSTOM_MODE_ENABLED: int = 1
MAV_MODE_FLAG_SAFETY_ARMED: int = 128
MAV_AUTOPILOT_ARDUPILOTMEGA: int = 3
ARM_PARAM_ENABLE: float = 1.0
ARM_PARAM_DISABLE: float = 0.0

COPTER_FLIGHT_MODES: dict[str, int] = {
    "STABILIZE": 0,
    "ACRO": 1,
    "ALT_HOLD": 2,
    "AUTO": 3,
    "GUIDED": 4,
    "LOITER": 5,
    "RTL": 6,
    "CIRCLE": 7,
    "LAND": 9,
    "DRIFT": 11,
    "SPORT": 13,
    "FLIP": 14,
    "AUTOTUNE": 15,
    "POSHOLD": 16,
    "BRAKE": 17,
}


def parse_vehicle_status(msg: Any, system_id: int) -> dict[str, int | str | bool]:
    """Read the actual armed flag and copter mode from a MAVLink heartbeat."""
    if not hasattr(msg, "base_mode") or not hasattr(msg, "custom_mode"):
        raise ValueError("HEARTBEAT missing base_mode or custom_mode")
    custom_mode = int(msg.custom_mode)
    mode = str(custom_mode)
    if getattr(msg, "autopilot", None) == MAV_AUTOPILOT_ARDUPILOTMEGA:
        mode = next(
            (name for name, number in COPTER_FLIGHT_MODES.items() if number == custom_mode),
            mode,
        )
    return {
        "system_id": system_id,
        "armed": bool(int(msg.base_mode) & MAV_MODE_FLAG_SAFETY_ARMED),
        "mode": mode,
    }


def parse_heartbeat(msg: Any, system_id: int, component_id: int) -> VehicleIdentity:
    """Parse a MAVLink HEARTBEAT message into a VehicleIdentity.

    Args:
        msg: MAVLink message object.
        system_id: MAVLink system ID.
        component_id: MAVLink component ID.

    Returns:
        VehicleIdentity instance.

    Raises:
        ValueError: If required attributes are missing.
    """
    if not hasattr(msg, "type") or not hasattr(msg, "autopilot"):
        raise ValueError("HEARTBEAT message missing 'type' or 'autopilot' field")

    vehicle_type = VehicleType.from_mav_type(int(msg.type))
    autopilot_type = AutopilotType.from_mav_autopilot(int(msg.autopilot))

    return VehicleIdentity(
        system_id=system_id,
        component_id=component_id,
        vehicle_type=vehicle_type,
        autopilot_type=autopilot_type,
        firmware_version="1.0.0",
    )


def parse_param_value(msg: Any) -> Parameter:
    """Parse a MAVLink PARAM_VALUE message into a Parameter instance.

    Args:
        msg: MAVLink PARAM_VALUE message.

    Returns:
        Parameter instance.

    Raises:
        ValueError: If required parameter fields are missing.
    """
    required_attrs = ("param_id", "param_value", "param_type", "param_index")
    if any(not hasattr(msg, attr) for attr in required_attrs):
        raise ValueError("PARAM_VALUE message missing required fields")

    param_id_raw = msg.param_id
    if isinstance(param_id_raw, bytes):
        param_id_str = param_id_raw.decode("utf-8", errors="ignore")
    else:
        param_id_str = str(param_id_raw)
    param_id = param_id_str.rstrip("\x00")

    return Parameter(
        param_id=param_id,
        value=float(msg.param_value),
        param_type=int(msg.param_type),
        param_index=int(msg.param_index),
    )


def parse_attitude(msg: Any) -> AttitudeData:
    """Parse a MAVLink ATTITUDE message into an AttitudeData instance.

    Args:
        msg: MAVLink ATTITUDE message.

    Returns:
        AttitudeData instance with roll, pitch, and yaw in radians.

    Raises:
        ValueError: If attitude fields are missing.
    """
    if not hasattr(msg, "roll") or not hasattr(msg, "pitch") or not hasattr(msg, "yaw"):
        raise ValueError("ATTITUDE message missing roll, pitch, or yaw")

    return AttitudeData(
        roll=float(msg.roll),
        pitch=float(msg.pitch),
        yaw=float(msg.yaw),
    )


def parse_gps(msg: Any) -> GpsData:
    """Parse a MAVLink GPS_RAW_INT message into a GpsData instance.

    Args:
        msg: MAVLink GPS_RAW_INT message.

    Returns:
        GpsData instance with latitude/longitude in degrees and altitude in meters.

    Raises:
        ValueError: If required GPS fields are missing.
    """
    required = ("lat", "lon", "alt", "fix_type", "satellites_visible")
    if any(not hasattr(msg, attr) for attr in required):
        raise ValueError("GPS message missing required coordinates or status fields")

    return GpsData(
        lat=float(msg.lat) / GPS_COORD_SCALE,
        lon=float(msg.lon) / GPS_COORD_SCALE,
        alt=float(msg.alt) / GPS_ALT_SCALE_M,
        fix_type=int(msg.fix_type),
        satellites=int(msg.satellites_visible),
    )


def parse_battery(msg: Any) -> BatteryData:
    """Parse a MAVLink SYS_STATUS or BATTERY_STATUS message into BatteryData.

    Args:
        msg: MAVLink message containing battery fields.

    Returns:
        BatteryData instance with voltage (V), current (A), and remaining (%).

    Raises:
        ValueError: If battery fields are missing.
    """
    required = ("current_battery", "battery_remaining")
    if any(not hasattr(msg, attr) for attr in required):
        raise ValueError("Battery message missing required fields")
    if hasattr(msg, "voltage_battery"):
        voltage = float(msg.voltage_battery)
        voltage = -1.0 if voltage == UNKNOWN_BATTERY_VOLTAGE else voltage / BATT_VOLT_SCALE
    elif hasattr(msg, "voltages"):
        cells = [v for v in msg.voltages if v != UNKNOWN_BATTERY_VOLTAGE]
        voltage = sum(cells) / BATT_VOLT_SCALE if cells else -1.0
    else:
        raise ValueError("Battery message missing voltage fields")

    return BatteryData(
        voltage=voltage,
        current=float(msg.current_battery) / BATT_AMP_SCALE if msg.current_battery >= 0 else -1.0,
        remaining=int(msg.battery_remaining),
    )


def parse_global_position(msg: Any) -> dict[str, float]:
    """Decode fused position (MSL altitude) and horizontal ground speed."""
    required = ("lat", "lon", "alt", "relative_alt", "vx", "vy")
    if any(not hasattr(msg, attr) for attr in required):
        raise ValueError("GLOBAL_POSITION_INT missing position or velocity fields")
    return {
        "lat": float(msg.lat) / GPS_COORD_SCALE,
        "lon": float(msg.lon) / GPS_COORD_SCALE,
        "alt": float(msg.alt) / GPS_ALT_SCALE_M,
        "relative_alt": float(msg.relative_alt) / GPS_ALT_SCALE_M,
        "speed": math.hypot(msg.vx, msg.vy) / VELOCITY_CM_PER_M,
    }


def parse_vfr_hud(msg: Any) -> dict[str, float]:
    """Decode HUD ground speed, MSL altitude, and vertical speed in SI units."""
    if any(not hasattr(msg, attr) for attr in ("groundspeed", "alt", "climb")):
        raise ValueError("VFR_HUD missing speed or altitude fields")
    return {"speed": float(msg.groundspeed), "alt": float(msg.alt), "climb": float(msg.climb)}


def create_message_interval_msg(
    target_system: int, target_component: int, message_id: int, rate_hz: int,
) -> Any:
    """Request a positive per-message frequency using MAV_CMD_SET_MESSAGE_INTERVAL."""
    if rate_hz <= 0:
        raise ValueError("Telemetry rate must be positive")
    return mavutil.mavlink.MAVLink(None).command_long_encode(
        target_system, target_component, MAV_CMD_SET_MESSAGE_INTERVAL, 0,
        message_id, MICROSECONDS_PER_SECOND / rate_hz, 0, 0, 0, 0, 0,
    )


def create_data_stream_msg(
    target_system: int, target_component: int, stream_id: int, rate_hz: int,
) -> Any:
    """Enable a legacy stream group at a positive frequency."""
    if rate_hz <= 0:
        raise ValueError("Telemetry rate must be positive")
    return mavutil.mavlink.MAVLink(None).request_data_stream_encode(
        target_system, target_component, stream_id, rate_hz, 1,
    )


def parse_rc_channels(msg: Any) -> list[int]:
    """Parse a MAVLink RC_CHANNELS message into an 18-channel list of PWM values.

    Args:
        msg: MAVLink RC_CHANNELS message.

    Returns:
        List of 18 raw integer PWM values.

    Raises:
        ValueError: If any channel attribute is missing.
    """
    channels: list[int] = []
    for i in range(1, NUM_RC_CHANNELS + 1):
        attr_name = f"chan{i}_raw"
        if not hasattr(msg, attr_name):
            raise ValueError(f"RC_CHANNELS missing '{attr_name}'")
        channels.append(int(getattr(msg, attr_name)))
    return channels


def create_mav_connection(endpoint: ConnectionEndpoint) -> Any:
    """Create a pymavlink connection from a ConnectionEndpoint descriptor.

    Args:
        endpoint: Endpoint specifying protocol, address, and port.

    Returns:
        MAVLink connection object (mavutil.mavlink_connection).
    """
    proto = endpoint.protocol.lower()
    if proto == "tcp":
        uri = f"tcp:{endpoint.address}:{endpoint.port}"
    elif proto == "udp":
        uri = f"udpin:{endpoint.address}:{endpoint.port}"
    else:
        uri = f"{proto}:{endpoint.address}:{endpoint.port}"

    logger.info("Opening MAVLink connection to %s", uri)
    return mavutil.mavlink_connection(uri)


def create_param_request_list_msg(
    target_system: int = 0,
    target_component: int = 0,
) -> Any:
    """Create a MAVLink PARAM_REQUEST_LIST message to query all parameters.

    Args:
        target_system: Target system ID (0 for broadcast).
        target_component: Target component ID (0 for broadcast).

    Returns:
        MAVLink PARAM_REQUEST_LIST message object.
    """
    mav = mavutil.mavlink.MAVLink(None)
    return mav.param_request_list_encode(target_system, target_component)


def create_param_set_msg(
    target_system: int,
    target_component: int,
    param_id: str,
    param_value: float,
    param_type: int = 9,
) -> Any:
    """Create a MAVLink PARAM_SET message.

    Args:
        target_system: Target vehicle system ID.
        target_component: Target vehicle component ID.
        param_id: Parameter name string.
        param_value: New float value.
        param_type: MAVLink parameter type code (default 9 = REAL32).

    Returns:
        MAVLink PARAM_SET message object.
    """
    mav = mavutil.mavlink.MAVLink(None)
    return mav.param_set_encode(
        target_system,
        target_component,
        param_id.encode("utf-8"),
        float(param_value),
        param_type,
    )


def create_rc_override_msg(
    target_system: int,
    target_component: int,
    throttle: int,
    steering: int = 1500,
    pitch: int = 0,
    yaw: int = 0,
) -> Any:
    """Create an RC_CHANNELS_OVERRIDE message.

    Args:
        target_system: Target system ID.
        target_component: Target component ID.
        throttle: PWM value for channel 3 (1000-2000).
        steering: PWM value for channel 1 (roll or steering, 1000-2000).
        pitch: PWM value for channel 2 (pitch, 1000-2000 or 0 for ignore).
        yaw: PWM value for channel 4 (yaw, 1000-2000 or 0 for ignore).

    Returns:
        MAVLink RC_CHANNELS_OVERRIDE message object.
    """
    mav = mavutil.mavlink.MAVLink(None)
    return mav.rc_channels_override_encode(
        target_system,
        target_component,
        steering,
        pitch,
        throttle,
        yaw,
        0,
        0,
        0,
        0,
    )


def create_arm_disarm_msg(
    target_system: int,
    target_component: int,
    arm: bool,
) -> Any:
    """Generate MAVLink COMMAND_LONG packet to arm or disarm the vehicle.

    Args:
        target_system: Target MAVLink system ID.
        target_component: Target MAVLink component ID.
        arm: True to arm (1.0), False to disarm (0.0).

    Returns:
        MAVLink COMMAND_LONG message object.
    """
    mav = mavutil.mavlink.MAVLink(None)
    param1 = ARM_PARAM_ENABLE if arm else ARM_PARAM_DISABLE
    return mav.command_long_encode(
        target_system,
        target_component,
        MAV_CMD_COMPONENT_ARM_DISARM,
        0,
        param1,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )


def create_set_mode_msg(
    target_system: int,
    target_component: int,
    mode: str | int,
) -> Any:
    """Generate MAVLink COMMAND_LONG packet to set vehicle flight mode.

    Args:
        target_system: Target MAVLink system ID.
        target_component: Target MAVLink component ID.
        mode: Flight mode name string or integer mode number.

    Returns:
        MAVLink COMMAND_LONG message object.
    """
    mav = mavutil.mavlink.MAVLink(None)
    if isinstance(mode, str):
        normalized = mode.upper()
        if normalized not in COPTER_FLIGHT_MODES:
            raise ValueError(f"Unknown flight mode: {mode}")
        mode_num = COPTER_FLIGHT_MODES[normalized]
    else:
        mode_num = int(mode)
    return mav.command_long_encode(
        target_system,
        target_component,
        MAV_CMD_DO_SET_MODE,
        0,
        float(MAV_MODE_FLAG_CUSTOM_MODE_ENABLED),
        float(mode_num),
        0.0,
        0.0,
        0.0,
        0.0,
        0.0,
    )

