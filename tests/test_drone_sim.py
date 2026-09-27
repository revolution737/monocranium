from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from src.core.protocol import get_simulator_mavlink_dialect
from src.core.types import ConnectionEndpoint
from src.simulators.drone_config import DEFAULT_DRONE_CONFIG
from src.simulators.drone_physics import DroneKinematics
from src.simulators.drone_sim import DroneMavlinkServer


def _decode_frame(frame: bytes) -> Any:
    """Decode one simulator frame through the protocol-owned dialect factory."""
    dialect = get_simulator_mavlink_dialect()
    return dialect.MAVLink(None).parse_buffer(frame)[0]


def test_drone_sim_initial_state() -> None:
    """Verify drone initial RC state defaults to (1500, 1500, 1500, 1500)."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG, port=5771, system_id=3)
    assert server.current_rc == (1500, 1500, 1500, 1500)
    assert server.client_count == 0


def test_drone_parameter_list_length() -> None:
    """Verify drone parameter list contains 18 parameters."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG)
    assert len(server._params) == 18


def test_drone_endpoint_property() -> None:
    """Verify endpoint property returns TCP port 5771 descriptor."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG, port=5771)
    expected = ConnectionEndpoint(address="127.0.0.1", port=5771, protocol="tcp")
    assert server.endpoint == expected


def test_drone_heartbeat_payload() -> None:
    """Verify generated heartbeat contains valid MAVLink v2 binary packet."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG, system_id=3)
    hb_bytes = server._create_heartbeat_bytes()
    assert isinstance(hb_bytes, bytes)
    assert len(hb_bytes) > 0
    # MAVLink v2 packet magic byte is 0xFD
    assert hb_bytes[0] == 0xFD
    # System ID matches system_id=3
    assert hb_bytes[5] == 3


def test_drone_handle_rc_override_4ch() -> None:
    """Verify _handle_rc_override modifies all 4 flight channels."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG)

    mock_msg = MagicMock()
    mock_msg.chan1_raw = 1420  # roll
    mock_msg.chan2_raw = 1580  # pitch
    mock_msg.chan3_raw = 1650  # throttle
    mock_msg.chan4_raw = 1510  # yaw
    server._handle_rc_override(mock_msg)

    assert server.current_rc == (1420, 1580, 1650, 1510)


def test_drone_handle_param_set() -> None:
    """Verify _handle_param_set modifies parameter value and returns reply."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG)

    mock_msg = MagicMock()
    mock_msg.param_id = b"PILOT_SPEED_UP\x00"
    mock_msg.param_value = 600.0

    reply = server._handle_param_set(mock_msg)
    assert reply is not None

    param = next(p for p in server._params if p["param_id"] == "PILOT_SPEED_UP")
    assert param["value"] == 600.0


def test_drone_handle_param_request_list() -> None:
    """Verify _handle_param_request_list generates 18 encoded PARAM_VALUE frames."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG)
    frames = server._handle_param_request_list()
    assert len(frames) == 18


def test_drone_telemetry_bytes_generation() -> None:
    """Verify attitude, gps, sys_status, and rc_channels byte generation."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG, system_id=3)

    att_bytes = server._create_attitude_bytes()
    assert isinstance(att_bytes, bytes) and len(att_bytes) > 0
    assert att_bytes[0] == 0xFD

    gps_bytes = server._create_gps_bytes()
    assert isinstance(gps_bytes, bytes) and len(gps_bytes) > 0
    assert gps_bytes[0] == 0xFD

    sys_bytes = server._create_sys_status_bytes()
    assert isinstance(sys_bytes, bytes) and len(sys_bytes) > 0
    assert sys_bytes[0] == 0xFD

    rc_bytes = server._create_rc_channels_bytes()
    assert isinstance(rc_bytes, bytes) and len(rc_bytes) > 0
    assert rc_bytes[0] == 0xFD


def test_drone_handle_rc_override_out_of_bounds() -> None:
    """Verify _handle_rc_override ignores out-of-range PWM values."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG)

    mock_msg = MagicMock()
    mock_msg.chan1_raw = 900
    mock_msg.chan2_raw = 2100
    mock_msg.chan3_raw = 0
    mock_msg.chan4_raw = 3000
    server._handle_rc_override(mock_msg)

    assert server.current_rc == (1500, 1500, 1500, 1500)


def test_drone_handle_param_set_unknown() -> None:
    """Verify _handle_param_set returns None for unknown parameter."""
    kin = DroneKinematics(DEFAULT_DRONE_CONFIG)
    server = DroneMavlinkServer(kin, DEFAULT_DRONE_CONFIG)

    mock_msg = MagicMock()
    mock_msg.param_id = b"NONEXISTENT\x00"
    mock_msg.param_value = 1.0

    reply = server._handle_param_set(mock_msg)
    assert reply is None


def test_drone_arm_command_updates_heartbeat_and_acknowledges() -> None:
    """The simulator reports the new armed state and acknowledges a valid command."""
    from src.core.protocol import MAV_CMD_COMPONENT_ARM_DISARM

    server = DroneMavlinkServer(DroneKinematics(DEFAULT_DRONE_CONFIG), DEFAULT_DRONE_CONFIG)
    command = MagicMock(command=MAV_CMD_COMPONENT_ARM_DISARM, param1=1.0)

    reply = server._handle_command_long(command)

    assert reply is not None
    assert _decode_frame(reply).result == 0
    assert server._armed is True
    assert _decode_frame(server._create_heartbeat_bytes()).base_mode & 128


def test_drone_unsupported_command_is_rejected_without_state_change() -> None:
    """Unknown commands receive a negative acknowledgement."""
    server = DroneMavlinkServer(DroneKinematics(DEFAULT_DRONE_CONFIG), DEFAULT_DRONE_CONFIG)

    reply = server._handle_command_long(MagicMock(command=9999))

    assert reply is not None
    assert _decode_frame(reply).result == 3
    assert server._armed is False


def test_drone_mode_command_updates_heartbeat() -> None:
    """Accepted flight modes appear in subsequent heartbeats."""
    from src.core.protocol import MAV_CMD_DO_SET_MODE

    server = DroneMavlinkServer(DroneKinematics(DEFAULT_DRONE_CONFIG), DEFAULT_DRONE_CONFIG)
    reply = server._handle_command_long(
        MagicMock(command=MAV_CMD_DO_SET_MODE, param2=2.0),
    )

    assert reply is not None
    assert _decode_frame(reply).result == 0
    assert _decode_frame(server._create_heartbeat_bytes()).custom_mode == 2


def test_drone_invalid_mode_is_denied() -> None:
    """Invalid modes preserve simulator state and return a denial."""
    from src.core.protocol import MAV_CMD_DO_SET_MODE

    server = DroneMavlinkServer(DroneKinematics(DEFAULT_DRONE_CONFIG), DEFAULT_DRONE_CONFIG)
    reply = server._handle_command_long(
        MagicMock(command=MAV_CMD_DO_SET_MODE, param2=999.0),
    )

    assert reply is not None
    assert _decode_frame(reply).result == 2
    assert _decode_frame(server._create_heartbeat_bytes()).custom_mode == 0

