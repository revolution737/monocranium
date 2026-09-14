from __future__ import annotations

from unittest.mock import MagicMock

from src.core.types import ConnectionEndpoint
from src.simulators.rover_config import DEFAULT_ROVER_CONFIG
from src.simulators.rover_physics import RoverKinematics
from src.simulators.rover_sim import RoverMavlinkServer


def test_rover_sim_initial_state() -> None:
    """Verify initial PWM state defaults to center (1500, 1500)."""
    kin = RoverKinematics(DEFAULT_ROVER_CONFIG)
    server = RoverMavlinkServer(kin, DEFAULT_ROVER_CONFIG)
    assert server.current_rc == (1500, 1500)
    assert server.client_count == 0


def test_parameter_list_length() -> None:
    """Verify internal parameter list initializes with 19 parameters."""
    kin = RoverKinematics(DEFAULT_ROVER_CONFIG)
    server = RoverMavlinkServer(kin, DEFAULT_ROVER_CONFIG)
    assert len(server._params) == 19


def test_endpoint_property() -> None:
    """Verify server endpoint property returns tcp 127.0.0.1 with correct port."""
    kin = RoverKinematics(DEFAULT_ROVER_CONFIG)
    server = RoverMavlinkServer(kin, DEFAULT_ROVER_CONFIG, port=5775)
    expected = ConnectionEndpoint(address="127.0.0.1", port=5775, protocol="tcp")
    assert server.endpoint == expected


def test_handle_rc_override_updates_state() -> None:
    """Verify _handle_rc_override modifies throttle and steering PWM."""
    kin = RoverKinematics(DEFAULT_ROVER_CONFIG)
    server = RoverMavlinkServer(kin, DEFAULT_ROVER_CONFIG)

    mock_msg = MagicMock()
    mock_msg.chan1_raw = 1750
    mock_msg.chan3_raw = 1650
    server._handle_rc_override(mock_msg)

    assert server.current_rc == (1650, 1750)


def test_handle_param_set_updates_value() -> None:
    """Verify _handle_param_set updates target parameter and returns reply bytes."""
    kin = RoverKinematics(DEFAULT_ROVER_CONFIG)
    server = RoverMavlinkServer(kin, DEFAULT_ROVER_CONFIG)

    mock_msg = MagicMock()
    mock_msg.param_id = b"CRUISE_SPEED\x00\x00\x00"
    mock_msg.param_value = 2.5

    reply_bytes = server._handle_param_set(mock_msg)
    assert reply_bytes is not None
    assert len(reply_bytes) > 0

    # Verify param updated in list
    param_entry = next(p for p in server._params if p["param_id"] == "CRUISE_SPEED")
    assert param_entry["value"] == 2.5


def test_handle_param_request_list_count() -> None:
    """Verify _handle_param_request_list produces exactly 19 encoded frames."""
    kin = RoverKinematics(DEFAULT_ROVER_CONFIG)
    server = RoverMavlinkServer(kin, DEFAULT_ROVER_CONFIG)

    frames = server._handle_param_request_list()
    assert len(frames) == 19
    for frame in frames:
        assert isinstance(frame, bytes)
        assert len(frame) > 0
