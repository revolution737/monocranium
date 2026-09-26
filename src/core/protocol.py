from __future__ import annotations

import logging
from typing import Any

from pymavlink import mavutil

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
    required = ("voltage_battery", "current_battery", "battery_remaining")
    if any(not hasattr(msg, attr) for attr in required):
        raise ValueError("Battery message missing required fields")

    return BatteryData(
        voltage=float(msg.voltage_battery) / BATT_VOLT_SCALE,
        current=float(msg.current_battery) / BATT_AMP_SCALE,
        remaining=int(msg.battery_remaining),
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
