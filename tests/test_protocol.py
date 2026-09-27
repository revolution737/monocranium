from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from src.core.protocol import (
    create_arm_disarm_msg,
    create_data_stream_msg,
    create_mav_connection,
    create_message_interval_msg,
    create_rc_override_msg,
    create_set_mode_msg,
    get_simulator_mavlink_dialect,
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
from src.core.types import AutopilotType, ConnectionEndpoint, VehicleType


def test_parse_vehicle_status_from_heartbeat() -> None:
    """The armed flag and mode reflect autopilot heartbeat fields."""
    assert parse_vehicle_status(SimpleNamespace(base_mode=128, custom_mode=5, autopilot=3), 1) == {
        "system_id": 1, "armed": True, "mode": "LOITER",
    }


def test_parse_vehicle_status_requires_fields() -> None:
    """Incomplete heartbeats do not create a false command state."""
    with pytest.raises(ValueError):
        parse_vehicle_status(SimpleNamespace(base_mode=0), 1)


def test_parse_vehicle_status_preserves_unknown_autopilot_mode() -> None:
    """A PX4 custom mode number must not be labeled as an ArduPilot mode."""
    assert parse_vehicle_status(
        SimpleNamespace(base_mode=0, custom_mode=5, autopilot=12), 2,
    )["mode"] == "5"


def test_simulator_dialect_exposes_message_classes() -> None:
    """Simulator packet synthesis uses the protocol-owned MAVLink dialect."""
    assert hasattr(get_simulator_mavlink_dialect(), "MAVLink")


def test_simulator_dialect_is_shared() -> None:
    """The factory consistently returns one dialect module."""
    assert get_simulator_mavlink_dialect() is get_simulator_mavlink_dialect()


def test_message_interval_packet() -> None:
    """Encode a 10 Hz targeted ATTITUDE request in microseconds."""
    msg = create_message_interval_msg(1, 1, 30, 10)
    assert (msg.command, msg.target_system, msg.target_component) == (511, 1, 1)
    assert (msg.param1, msg.param2) == (30, 100000)


def test_message_interval_rejects_invalid_rate() -> None:
    """Prevent invalid rate requests from reaching the transport."""
    with pytest.raises(ValueError):
        create_message_interval_msg(1, 1, 30, 0)


def test_legacy_stream_packet() -> None:
    """Legacy fallback enables the targeted EXTRA1 group."""
    msg = create_data_stream_msg(7, 1, 10, 10)
    assert (msg.target_system, msg.req_stream_id, msg.req_message_rate) == (7, 10, 10)
    assert msg.start_stop == 1


def test_legacy_stream_rejects_invalid_rate() -> None:
    """Reject a negative legacy stream rate."""
    with pytest.raises(ValueError):
        create_data_stream_msg(1, 1, 10, -1)


def test_global_position_units() -> None:
    """Convert position and horizontal velocity into dashboard units."""
    msg = SimpleNamespace(lat=10000000, lon=20000000, alt=120000, relative_alt=3000,
                          vx=300, vy=400)
    assert parse_global_position(msg) == {
        "lat": 1.0, "lon": 2.0, "alt": 120.0, "relative_alt": 3.0, "speed": 5.0,
    }


def test_global_position_missing_fields() -> None:
    """Malformed position frames fail explicitly."""
    with pytest.raises(ValueError):
        parse_global_position(SimpleNamespace(lat=0))


def test_vfr_hud_units() -> None:
    """HUD altitude is MSL metres and groundspeed is metres per second."""
    assert parse_vfr_hud(SimpleNamespace(groundspeed=4, alt=120, climb=2)) == {
        "speed": 4.0, "alt": 120.0, "climb": 2.0,
    }


def test_vfr_hud_missing_fields() -> None:
    """Malformed HUD frames fail explicitly."""
    with pytest.raises(ValueError):
        parse_vfr_hud(SimpleNamespace())


def test_battery_status_cell_voltages() -> None:
    """BATTERY_STATUS cell voltages exclude unused UINT16_MAX entries."""
    msg = SimpleNamespace(voltages=[4000, 4100, 65535], current_battery=125,
                          battery_remaining=80)
    battery = parse_battery(msg)
    assert battery.voltage == 8.1
    assert battery.current == 1.25


def test_battery_status_unknown_voltage() -> None:
    """Unknown cell voltages remain an unknown sentinel, not 655 volts."""
    msg = SimpleNamespace(voltages=[65535], current_battery=-1, battery_remaining=-1)
    assert parse_battery(msg).voltage == -1


def test_parse_heartbeat_rover() -> None:
    """Verify parse_heartbeat handles MAV_TYPE_GROUND_ROVER."""
    msg = MagicMock()
    msg.type = 10
    msg.autopilot = 0
    identity = parse_heartbeat(msg, system_id=2, component_id=1)
    assert identity.system_id == 2
    assert identity.component_id == 1
    assert identity.vehicle_type == VehicleType.ROVER
    assert identity.autopilot_type == AutopilotType.GENERIC


def test_parse_heartbeat_copter() -> None:
    """Verify parse_heartbeat handles MAV_TYPE_QUADROTOR with ArduPilot."""
    msg = MagicMock()
    msg.type = 2
    msg.autopilot = 3
    identity = parse_heartbeat(msg, system_id=3, component_id=1)
    assert identity.system_id == 3
    assert identity.component_id == 1
    assert identity.vehicle_type == VehicleType.COPTER
    assert identity.autopilot_type == AutopilotType.ARDUPILOT


def test_parse_heartbeat_unknown_type() -> None:
    """Verify parse_heartbeat handles unknown type safely."""
    msg = MagicMock()
    msg.type = 99
    msg.autopilot = 3
    identity = parse_heartbeat(msg, system_id=5, component_id=1)
    assert identity.vehicle_type == VehicleType.UNKNOWN
    assert identity.autopilot_type == AutopilotType.ARDUPILOT


def test_parse_heartbeat_missing_field() -> None:
    """Verify parse_heartbeat raises ValueError if fields are missing."""
    msg = MagicMock(spec=[])
    with pytest.raises(ValueError, match="missing 'type' or 'autopilot'"):
        parse_heartbeat(msg, system_id=1, component_id=1)


def test_parse_param_value() -> None:
    """Verify parse_param_value parses valid message fields."""
    msg = MagicMock()
    msg.param_id = "WHEEL_DIA_MM"
    msg.param_value = 130.0
    msg.param_type = 9
    msg.param_index = 1
    param = parse_param_value(msg)
    assert param.param_id == "WHEEL_DIA_MM"
    assert param.value == 130.0
    assert param.param_type == 9
    assert param.param_index == 1


def test_parse_param_value_strips_nulls() -> None:
    """Verify parse_param_value strips trailing null bytes from bytes/strings."""
    msg = MagicMock()
    msg.param_id = b"SPEED\x00\x00\x00"
    msg.param_value = 2.5
    msg.param_type = 9
    msg.param_index = 3
    param = parse_param_value(msg)
    assert param.param_id == "SPEED"


def test_parse_attitude() -> None:
    """Verify parse_attitude extracts roll, pitch, yaw in radians."""
    msg = MagicMock()
    msg.roll = 0.1
    msg.pitch = -0.2
    msg.yaw = 1.57
    att = parse_attitude(msg)
    assert att.roll == pytest.approx(0.1)
    assert att.pitch == pytest.approx(-0.2)
    assert att.yaw == pytest.approx(1.57)


def test_parse_gps() -> None:
    """Verify parse_gps scales 1e7 coordinates and millimeter altitude."""
    msg = MagicMock()
    msg.lat = 286139000
    msg.lon = 772090000
    msg.alt = 15500
    msg.fix_type = 3
    msg.satellites_visible = 12
    gps = parse_gps(msg)
    assert gps.lat == pytest.approx(28.6139)
    assert gps.lon == pytest.approx(77.2090)
    assert gps.alt == pytest.approx(15.5)
    assert gps.fix_type == 3
    assert gps.satellites == 12


def test_parse_gps_missing_field() -> None:
    """Verify parse_gps raises ValueError when required fields are missing."""
    msg = MagicMock(spec=["lat", "lon"])
    with pytest.raises(ValueError, match="missing required"):
        parse_gps(msg)


def test_parse_battery() -> None:
    """Verify parse_battery scales millivolts and centiamperes."""
    msg = MagicMock()
    msg.voltage_battery = 11100
    msg.current_battery = 250
    msg.battery_remaining = 85
    batt = parse_battery(msg)
    assert batt.voltage == pytest.approx(11.1)
    assert batt.current == pytest.approx(2.5)
    assert batt.remaining == 85


def test_parse_rc_channels() -> None:
    """Verify parse_rc_channels parses all 18 channels."""
    msg = MagicMock()
    for i in range(1, 19):
        setattr(msg, f"chan{i}_raw", 1000 + (i * 50))
    channels = parse_rc_channels(msg)
    assert len(channels) == 18
    assert channels[0] == 1050
    assert channels[17] == 1900


@patch("src.core.protocol.mavutil.mavlink_connection")
def test_create_mav_connection_tcp(mock_mavconn: MagicMock) -> None:
    """Verify create_mav_connection opens tcp URI."""
    endpoint = ConnectionEndpoint(address="127.0.0.1", port=5770, protocol="tcp")
    create_mav_connection(endpoint)
    mock_mavconn.assert_called_once_with("tcp:127.0.0.1:5770")


@patch("src.core.protocol.mavutil.mavlink_connection")
def test_create_mav_connection_udp(mock_mavconn: MagicMock) -> None:
    """Verify create_mav_connection opens udpin URI."""
    endpoint = ConnectionEndpoint(address="0.0.0.0", port=14550, protocol="udp")
    create_mav_connection(endpoint)
    mock_mavconn.assert_called_once_with("udpin:0.0.0.0:14550")


def test_create_rc_override_msg_rover_compat() -> None:
    """Verify create_rc_override_msg defaults pitch and yaw to 0 for rover."""
    msg = create_rc_override_msg(target_system=2, target_component=1, throttle=1700, steering=1300)
    assert msg.target_system == 2
    assert msg.target_component == 1
    assert msg.chan1_raw == 1300  # steering
    assert msg.chan2_raw == 0     # pitch unassigned
    assert msg.chan3_raw == 1700  # throttle
    assert msg.chan4_raw == 0     # yaw unassigned


def test_create_rc_override_msg_drone_4ch() -> None:
    """Verify create_rc_override_msg populates all 4 flight channels for drone."""
    msg = create_rc_override_msg(
        target_system=3,
        target_component=1,
        throttle=1650,
        steering=1420,
        pitch=1580,
        yaw=1510,
    )
    assert msg.target_system == 3
    assert msg.target_component == 1
    assert msg.chan1_raw == 1420  # roll
    assert msg.chan2_raw == 1580  # pitch
    assert msg.chan3_raw == 1650  # throttle
    assert msg.chan4_raw == 1510  # yaw


def test_create_arm_disarm_msg_arm() -> None:
    """Verify create_arm_disarm_msg encodes COMMAND_LONG with param1=1.0 when arming."""
    msg = create_arm_disarm_msg(target_system=3, target_component=1, arm=True)
    assert msg.target_system == 3
    assert msg.target_component == 1
    assert msg.command == 400
    assert msg.param1 == 1.0


def test_create_arm_disarm_msg_disarm() -> None:
    """Verify create_arm_disarm_msg encodes COMMAND_LONG with param1=0.0 when disarming."""
    msg = create_arm_disarm_msg(target_system=2, target_component=1, arm=False)
    assert msg.target_system == 2
    assert msg.target_component == 1
    assert msg.command == 400
    assert msg.param1 == 0.0


def test_create_set_mode_msg_named_mode() -> None:
    """Verify create_set_mode_msg resolves mode names (ALT_HOLD -> 2)."""
    msg = create_set_mode_msg(target_system=3, target_component=1, mode="ALT_HOLD")
    assert msg.target_system == 3
    assert msg.target_component == 1
    assert msg.command == 176
    assert msg.param1 == 1.0
    assert msg.param2 == 2.0


def test_create_set_mode_msg_integer_mode() -> None:
    """Verify create_set_mode_msg accepts raw integer mode IDs."""
    msg = create_set_mode_msg(target_system=3, target_component=1, mode=5)
    assert msg.target_system == 3
    assert msg.target_component == 1
    assert msg.command == 176
    assert msg.param1 == 1.0
    assert msg.param2 == 5.0


def test_create_set_mode_msg_rejects_unknown_name() -> None:
    """An invalid mode must never silently switch a copter to STABILIZE."""
    with pytest.raises(ValueError, match="Unknown flight mode"):
        create_set_mode_msg(target_system=3, target_component=1, mode="UNKNOWN_CUSTOM")

