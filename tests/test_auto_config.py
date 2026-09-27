from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.auto_config import AutoConfigEngine
from src.core.parameter_store import ParameterStore
from src.core.telemetry_bus import TelemetryBus
from src.core.telemetry_streams import TelemetryStreams
from src.core.types import (
    AutopilotType,
    ConnectionEndpoint,
    ConnectionState,
    Parameter,
    VehicleIdentity,
    VehicleType,
)
from src.core.vehicle_registry import VehicleRegistry


@pytest.mark.asyncio
async def test_simulator_without_interval_ack_keeps_telemetry_and_parameters(
    auto_engine: AutoConfigEngine, telemetry_bus: TelemetryBus,
) -> None:
    """The existing ArduPilot-like simulator may ignore new requests without breaking data."""
    auto_engine._streams = TelemetryStreams(ack_timeout_s=0.001)
    conn = MagicMock()
    conn.endpoint = ConnectionEndpoint("127.0.0.1", 5771, "tcp")
    conn.send_message = AsyncMock()
    await auto_engine._process_heartbeat(conn, SimpleNamespace(type=2, autopilot=3), 3, 1)
    received = AsyncMock()
    await telemetry_bus.subscribe("telemetry.attitude", received)
    await auto_engine._handle_incoming_msg(conn, SimpleNamespace(
        get_type=lambda: "ATTITUDE", get_srcSystem=lambda: 3, get_srcComponent=lambda: 1,
        roll=0.1, pitch=0.2, yaw=0.3,
    ))
    await asyncio.gather(*auto_engine._parameter_tasks)
    received.assert_awaited_once()
    kinds = [call.args[0].get_type() for call in conn.send_message.await_args_list]
    assert kinds == ["COMMAND_LONG", *(["REQUEST_DATA_STREAM"] * 5), "PARAM_REQUEST_LIST"]


@pytest.mark.asyncio
async def test_parameter_download_waits_for_stream_negotiation(
    auto_engine: AutoConfigEngine,
) -> None:
    """A parameter flood must not delay stream command acknowledgments."""
    conn = MagicMock()
    conn.send_message = AsyncMock()
    conn.endpoint = ConnectionEndpoint("127.0.0.1", 5760, "tcp")
    pending = asyncio.get_running_loop().create_future()
    auto_engine._streams = MagicMock()
    auto_engine._streams.start.return_value = pending
    msg = SimpleNamespace(type=2, autopilot=3)
    await auto_engine._process_heartbeat(conn, msg, 1, 1)
    conn.send_message.assert_not_awaited()
    pending.set_result(None)
    await asyncio.sleep(0)
    assert conn.send_message.await_args.args[0].get_type() == "PARAM_REQUEST_LIST"


@pytest.mark.asyncio
async def test_disconnect_removes_stale_vehicle_and_parameters(
    auto_engine: AutoConfigEngine, vehicle_registry: VehicleRegistry,
    param_store: ParameterStore, telemetry_bus: TelemetryBus,
) -> None:
    """A stopped SITL cannot remain discoverable with cached parameters."""
    conn = MagicMock()
    conn.endpoint = ConnectionEndpoint("127.0.0.1", 5760, "tcp")
    conn.send_message = AsyncMock()
    auto_engine._streams = MagicMock()
    auto_engine._streams.start.return_value = None
    await auto_engine._process_heartbeat(conn, SimpleNamespace(type=2, autopilot=3), 1, 1)
    await param_store.upsert(1, Parameter("ARMING_CHECK", 1.0, 9, 0))
    lost = AsyncMock()
    await telemetry_bus.subscribe("vehicle.lost", lost)
    await auto_engine._on_connection_state(conn, ConnectionState.DISCONNECTED)
    assert not vehicle_registry.is_registered(1)
    assert param_store.get_all(1) == []
    lost.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize("kind,fields,event,expected", [
    ("GLOBAL_POSITION_INT", {"lat": 10000000, "lon": 20000000, "alt": 10000,
     "relative_alt": 2000, "vx": 300, "vy": 400}, "telemetry.position", {"speed": 5.0}),
    ("VFR_HUD", {"groundspeed": 4.0, "alt": 10.0, "climb": 1.0},
     "telemetry.hud", {"speed": 4.0}),
    ("BATTERY_STATUS", {"voltages": [12000, 65535], "current_battery": 100,
     "battery_remaining": 90}, "telemetry.battery", {"voltage": 12.0}),
])
async def test_new_telemetry_reaches_bus(
    auto_engine: AutoConfigEngine, telemetry_bus: TelemetryBus,
    kind: str, fields: dict[str, Any], event: str, expected: dict[str, Any],
) -> None:
    """Received position, HUD, and cell battery messages reach subscribers."""
    events = []

    async def capture(name: str, data: dict[str, Any]) -> None:
        events.append(data)

    await telemetry_bus.subscribe(event, capture)
    msg = SimpleNamespace(**fields, get_type=lambda: kind,
                          get_srcSystem=lambda: 1, get_srcComponent=lambda: 1)
    await auto_engine._handle_incoming_msg(MagicMock(), msg)
    assert len(events) == 1
    assert events[0]["system_id"] == 1
    for key, value in expected.items():
        assert events[0][key] == value


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["GLOBAL_POSITION_INT", "VFR_HUD"])
async def test_malformed_telemetry_is_not_published(
    auto_engine: AutoConfigEngine, telemetry_bus: TelemetryBus, kind: str,
) -> None:
    """Malformed position and HUD messages are logged rather than published."""
    callback = AsyncMock()
    await telemetry_bus.subscribe("telemetry.position", callback)
    await telemetry_bus.subscribe("telemetry.hud", callback)
    msg = SimpleNamespace(get_type=lambda: kind, get_srcSystem=lambda: 1,
                          get_srcComponent=lambda: 1)
    await auto_engine._handle_incoming_msg(MagicMock(), msg)
    callback.assert_not_awaited()


@pytest.fixture
def mock_conn_mgr() -> MagicMock:
    """Mock ConnectionManager fixture."""
    mgr = MagicMock()
    mgr.list_connections.return_value = []
    return mgr


@pytest.fixture
def auto_engine(
    mock_conn_mgr: MagicMock,
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    telemetry_bus: TelemetryBus,
) -> AutoConfigEngine:
    """Provide configured AutoConfigEngine instance."""
    return AutoConfigEngine(mock_conn_mgr, vehicle_registry, param_store, telemetry_bus)


@pytest.mark.asyncio
async def test_auto_config_heartbeat_registers_vehicle(
    auto_engine: AutoConfigEngine,
    vehicle_registry: VehicleRegistry,
) -> None:
    """Verify incoming heartbeat registers vehicle in registry and sends parameter query."""
    mock_conn = MagicMock()
    mock_conn.endpoint = ConnectionEndpoint("127.0.0.1", 5770, "tcp")
    mock_conn.send_message = AsyncMock()

    hb_msg = MagicMock()
    hb_msg.get_type.return_value = "HEARTBEAT"
    hb_msg.get_srcSystem.return_value = 2
    hb_msg.get_srcComponent.return_value = 1
    hb_msg.type = 10
    hb_msg.autopilot = 0

    await auto_engine._handle_incoming_msg(mock_conn, hb_msg)

    assert vehicle_registry.is_registered(2)
    identity = vehicle_registry.get(2)
    assert identity.vehicle_type == VehicleType.ROVER
    assert mock_conn.send_message.await_count == 1


@pytest.mark.asyncio
async def test_auto_config_param_value_updates_store(
    auto_engine: AutoConfigEngine,
    param_store: ParameterStore,
) -> None:
    """Verify incoming PARAM_VALUE updates ParameterStore."""
    mock_conn = MagicMock()
    msg = MagicMock()
    msg.get_type.return_value = "PARAM_VALUE"
    msg.get_srcSystem.return_value = 2
    msg.param_id = "WHEEL_DIA_MM"
    msg.param_value = 130.0
    msg.param_type = 9
    msg.param_index = 1

    await auto_engine._handle_incoming_msg(mock_conn, msg)

    param = param_store.get(2, "WHEEL_DIA_MM")
    assert param.value == 130.0


@pytest.mark.asyncio
async def test_auto_config_telemetry_published_to_bus(
    auto_engine: AutoConfigEngine,
    telemetry_bus: TelemetryBus,
) -> None:
    """Verify incoming ATTITUDE messages are parsed and broadcast on bus."""
    attitude_events: list[dict[str, Any]] = []

    async def on_att(event: str, data: dict[str, Any]) -> None:
        attitude_events.append(data)

    await telemetry_bus.subscribe("telemetry.attitude", on_att)

    mock_conn = MagicMock()
    msg = MagicMock()
    msg.get_type.return_value = "ATTITUDE"
    msg.get_srcSystem.return_value = 2
    msg.roll = 0.05
    msg.pitch = -0.1
    msg.yaw = 1.2

    await auto_engine._handle_incoming_msg(mock_conn, msg)

    assert len(attitude_events) == 1
    assert attitude_events[0]["system_id"] == 2
    assert attitude_events[0]["yaw"] == 1.2


@pytest.mark.asyncio
async def test_auto_config_run_scan_timeout(
    auto_engine: AutoConfigEngine,
    mock_conn_mgr: MagicMock,
) -> None:
    """Verify run_scan returns None when timeout expires without discovery."""
    mock_conn = MagicMock()
    mock_conn.endpoint = ConnectionEndpoint("127.0.0.1", 9999, "tcp")
    mock_conn_mgr.add_connection = AsyncMock(return_value=mock_conn)

    endpoint = ConnectionEndpoint("127.0.0.1", 9999, "tcp")
    result = await auto_engine.run_scan(endpoint, timeout_s=0.1)
    assert result is None


@pytest.mark.asyncio
async def test_auto_config_send_rc_override_and_set_param(
    auto_engine: AutoConfigEngine,
    mock_conn_mgr: MagicMock,
) -> None:
    """An unrelated offline endpoint must not block RC or parameter writes."""
    mock_conn = MagicMock()
    mock_conn.endpoint = ConnectionEndpoint("127.0.0.1", 5770, "tcp")
    mock_conn.state = ConnectionState.CONNECTED
    mock_conn.send_message = AsyncMock()
    auto_engine._discovered_identities[("127.0.0.1", 5770)] = VehicleIdentity(
        2, 1, VehicleType.ROVER, AutopilotType.ARDUPILOT, "test",
    )
    offline = MagicMock()
    offline.endpoint = ConnectionEndpoint("127.0.0.1", 5771, "tcp")
    offline.send_message = AsyncMock(side_effect=ConnectionError("offline"))
    mock_conn_mgr.list_connections.return_value = [offline, mock_conn]

    await auto_engine.send_rc_override(2, throttle_pwm=1700, steering_pwm=1600)
    assert mock_conn.send_message.await_count == 1

    await auto_engine.set_parameter(2, "CRUISE_SPEED", 2.0)
    assert mock_conn.send_message.await_count == 2
    offline.send_message.assert_not_awaited()


@pytest.mark.asyncio
async def test_auto_config_send_rc_override_4ch(
    auto_engine: AutoConfigEngine,
    mock_conn_mgr: MagicMock,
) -> None:
    """Verify send_rc_override transmits all 4 channels for drones."""
    mock_conn = MagicMock()
    mock_conn.endpoint = ConnectionEndpoint("127.0.0.1", 5771, "tcp")
    mock_conn.state = ConnectionState.CONNECTED
    auto_engine._discovered_identities[("127.0.0.1", 5771)] = VehicleIdentity(
        3, 1, VehicleType.COPTER, AutopilotType.ARDUPILOT, "test",
    )
    mock_conn.send_message = AsyncMock()
    mock_conn_mgr.list_connections.return_value = [mock_conn]

    await auto_engine.send_rc_override(
        system_id=3,
        throttle_pwm=1600,
        steering_pwm=1450,
        pitch_pwm=1550,
        yaw_pwm=1520,
    )
    assert mock_conn.send_message.await_count == 1
    sent_msg = mock_conn.send_message.await_args[0][0]
    assert sent_msg.chan1_raw == 1450
    assert sent_msg.chan2_raw == 1550
    assert sent_msg.chan3_raw == 1600
    assert sent_msg.chan4_raw == 1520


@pytest.mark.asyncio
async def test_rc_and_parameter_writes_require_a_connected_target(
    auto_engine: AutoConfigEngine,
) -> None:
    """Undiscovered targets must report failure instead of silently succeeding."""
    with pytest.raises(ConnectionError, match="no connected MAVLink endpoint"):
        await auto_engine.send_rc_override(99, throttle_pwm=1500)
    with pytest.raises(ConnectionError, match="no connected MAVLink endpoint"):
        await auto_engine.set_parameter(99, "CRUISE_SPEED", 2.0)


@pytest.mark.asyncio
async def test_auto_config_arm_vehicle(
    auto_engine: AutoConfigEngine,
    mock_conn_mgr: MagicMock,
) -> None:
    """Verify arm_vehicle transmits COMMAND_LONG with arm and disarm payloads."""
    mock_conn = MagicMock()
    mock_conn.endpoint = ConnectionEndpoint("127.0.0.1", 5760, "tcp")
    mock_conn.state = ConnectionState.CONNECTED
    auto_engine._discovered_identities[(mock_conn.endpoint.address, mock_conn.endpoint.port)] = (
        VehicleIdentity(3, 1, VehicleType.COPTER, AutopilotType.ARDUPILOT, "test")
    )
    sent = []

    async def accept(msg: Any) -> None:
        sent.append(msg)
        await auto_engine._handle_incoming_msg(mock_conn, SimpleNamespace(
            get_type=lambda: "COMMAND_ACK", get_srcSystem=lambda: 3,
            get_srcComponent=lambda: 1, command=msg.command, result=0,
        ))

    mock_conn.send_message = accept
    mock_conn_mgr.list_connections.return_value = [mock_conn]

    await auto_engine.arm_vehicle(system_id=3, arm=True)
    assert len(sent) == 1
    arm_msg = sent[-1]
    assert arm_msg.command == 400
    assert arm_msg.param1 == 1.0

    await auto_engine.arm_vehicle(system_id=3, arm=False)
    assert len(sent) == 2
    disarm_msg = sent[-1]
    assert disarm_msg.command == 400
    assert disarm_msg.param1 == 0.0


@pytest.mark.asyncio
async def test_auto_config_set_mode(
    auto_engine: AutoConfigEngine,
    mock_conn_mgr: MagicMock,
) -> None:
    """Verify set_mode transmits COMMAND_LONG with correct mode identifiers."""
    mock_conn = MagicMock()
    mock_conn.endpoint = ConnectionEndpoint("127.0.0.1", 5760, "tcp")
    mock_conn.state = ConnectionState.CONNECTED
    auto_engine._discovered_identities[(mock_conn.endpoint.address, mock_conn.endpoint.port)] = (
        VehicleIdentity(3, 1, VehicleType.COPTER, AutopilotType.ARDUPILOT, "test")
    )
    sent = []

    async def accept(msg: Any) -> None:
        sent.append(msg)
        await auto_engine._handle_incoming_msg(mock_conn, SimpleNamespace(
            get_type=lambda: "COMMAND_ACK", get_srcSystem=lambda: 3,
            get_srcComponent=lambda: 1, command=msg.command, result=0,
        ))

    mock_conn.send_message = accept
    mock_conn_mgr.list_connections.return_value = [mock_conn]

    await auto_engine.set_mode(system_id=3, mode="LOITER")
    assert len(sent) == 1
    mode_msg = sent[-1]
    assert mode_msg.command == 176
    assert mode_msg.param2 == 5.0

    await auto_engine.set_mode(system_id=3, mode=6)
    assert len(sent) == 2
    rtl_msg = sent[-1]
    assert rtl_msg.command == 176
    assert rtl_msg.param2 == 6.0


@pytest.mark.asyncio
async def test_arm_rejection_is_reported(
    auto_engine: AutoConfigEngine, mock_conn_mgr: MagicMock,
) -> None:
    """A rejected ArduPilot command cannot be reported as armed."""
    conn = MagicMock()
    conn.endpoint = ConnectionEndpoint("127.0.0.1", 5760, "tcp")
    conn.state = ConnectionState.CONNECTED
    auto_engine._discovered_identities[(conn.endpoint.address, conn.endpoint.port)] = (
        VehicleIdentity(1, 1, VehicleType.COPTER, AutopilotType.ARDUPILOT, "test")
    )
    mock_conn_mgr.list_connections.return_value = [conn]

    async def reject(msg: Any) -> None:
        await auto_engine._handle_incoming_msg(conn, SimpleNamespace(
            get_type=lambda: "COMMAND_ACK", get_srcSystem=lambda: 1,
            get_srcComponent=lambda: 1, command=msg.command, result=4,
        ))

    conn.send_message = reject
    with pytest.raises(ValueError, match="rejected"):
        await auto_engine.arm_vehicle(1, True)


@pytest.mark.asyncio
async def test_arm_requires_connected_target(auto_engine: AutoConfigEngine) -> None:
    """No matching live vehicle means no successful command response."""
    with pytest.raises(ConnectionError):
        await auto_engine.arm_vehicle(99, True)


@pytest.mark.asyncio
async def test_mode_requires_acknowledgement(
    auto_engine: AutoConfigEngine, mock_conn_mgr: MagicMock,
) -> None:
    """A sent mode command without COMMAND_ACK is a failure."""
    conn = MagicMock()
    conn.endpoint = ConnectionEndpoint("127.0.0.1", 5760, "tcp")
    conn.state = ConnectionState.CONNECTED
    conn.send_message = AsyncMock()
    auto_engine._discovered_identities[(conn.endpoint.address, conn.endpoint.port)] = (
        VehicleIdentity(1, 1, VehicleType.COPTER, AutopilotType.ARDUPILOT, "test")
    )
    mock_conn_mgr.list_connections.return_value = [conn]
    with patch("src.core.auto_config.COMMAND_ACK_TIMEOUT_S", 0.001):
        with pytest.raises(TimeoutError, match="did not acknowledge"):
            await auto_engine.set_mode(1, "LOITER")


@pytest.mark.asyncio
async def test_heartbeat_publishes_actual_arm_and_mode(
    auto_engine: AutoConfigEngine, telemetry_bus: TelemetryBus,
) -> None:
    """Dashboard command state comes from vehicle heartbeat, not button clicks."""
    conn = MagicMock()
    conn.endpoint = ConnectionEndpoint("127.0.0.1", 5760, "tcp")
    conn.send_message = AsyncMock()
    auto_engine._streams = MagicMock()
    auto_engine._streams.start.return_value = None
    status = AsyncMock()
    await telemetry_bus.subscribe("vehicle.status", status)
    await auto_engine._process_heartbeat(
        conn, SimpleNamespace(type=2, autopilot=3, base_mode=128, custom_mode=5), 1, 1,
    )
    status.assert_awaited_once_with(
        "vehicle.status", {"system_id": 1, "armed": True, "mode": "LOITER"},
    )

