from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.auto_config import AutoConfigEngine
from src.core.parameter_store import ParameterStore
from src.core.telemetry_bus import TelemetryBus
from src.core.types import ConnectionEndpoint, VehicleType
from src.core.vehicle_registry import VehicleRegistry


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
    """Verify send_rc_override and set_parameter send MAVLink messages."""
    mock_conn = MagicMock()
    mock_conn.send_message = AsyncMock()
    mock_conn_mgr.list_connections.return_value = [mock_conn]

    await auto_engine.send_rc_override(2, throttle_pwm=1700, steering_pwm=1600)
    assert mock_conn.send_message.await_count == 1

    await auto_engine.set_parameter(2, "CRUISE_SPEED", 2.0)
    assert mock_conn.send_message.await_count == 2


@pytest.mark.asyncio
async def test_auto_config_send_rc_override_4ch(
    auto_engine: AutoConfigEngine,
    mock_conn_mgr: MagicMock,
) -> None:
    """Verify send_rc_override transmits all 4 channels for drones."""
    mock_conn = MagicMock()
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
async def test_auto_config_arm_vehicle(
    auto_engine: AutoConfigEngine,
    mock_conn_mgr: MagicMock,
) -> None:
    """Verify arm_vehicle transmits COMMAND_LONG with arm and disarm payloads."""
    mock_conn = MagicMock()
    mock_conn.send_message = AsyncMock()
    mock_conn_mgr.list_connections.return_value = [mock_conn]

    await auto_engine.arm_vehicle(system_id=3, arm=True)
    assert mock_conn.send_message.await_count == 1
    arm_msg = mock_conn.send_message.await_args[0][0]
    assert arm_msg.command == 400
    assert arm_msg.param1 == 1.0

    await auto_engine.arm_vehicle(system_id=3, arm=False)
    assert mock_conn.send_message.await_count == 2
    disarm_msg = mock_conn.send_message.await_args[0][0]
    assert disarm_msg.command == 400
    assert disarm_msg.param1 == 0.0


@pytest.mark.asyncio
async def test_auto_config_set_mode(
    auto_engine: AutoConfigEngine,
    mock_conn_mgr: MagicMock,
) -> None:
    """Verify set_mode transmits COMMAND_LONG with correct mode identifiers."""
    mock_conn = MagicMock()
    mock_conn.send_message = AsyncMock()
    mock_conn_mgr.list_connections.return_value = [mock_conn]

    await auto_engine.set_mode(system_id=3, mode="LOITER")
    assert mock_conn.send_message.await_count == 1
    mode_msg = mock_conn.send_message.await_args[0][0]
    assert mode_msg.command == 176
    assert mode_msg.param2 == 5.0

    await auto_engine.set_mode(system_id=3, mode=6)
    assert mock_conn.send_message.await_count == 2
    rtl_msg = mock_conn.send_message.await_args[0][0]
    assert rtl_msg.command == 176
    assert rtl_msg.param2 == 6.0

