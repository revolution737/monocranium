from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from src.core.auto_config import AutoConfigEngine
from src.core.parameter_store import ParameterStore
from src.core.telemetry_bus import TelemetryBus
from src.core.types import Parameter, VehicleIdentity
from src.core.vehicle_registry import VehicleRegistry
from src.server.http_server import HttpServer
from src.server.ws_handlers import dispatch_command
from src.server.ws_server import WebSocketServer


@pytest.fixture
def mock_auto_config() -> MagicMock:
    """Mock AutoConfigEngine fixture."""
    engine = MagicMock(spec=AutoConfigEngine)
    engine.send_rc_override = AsyncMock()
    engine.set_parameter = AsyncMock()
    engine.run_full_scan = AsyncMock(return_value=[])
    engine.arm_vehicle = AsyncMock()
    engine.set_mode = AsyncMock()
    return engine


@pytest.fixture
def mock_conn_manager() -> MagicMock:
    """Mock ConnectionManager fixture."""
    mgr = MagicMock()
    mgr.list_connections.return_value = []
    return mgr


@pytest.mark.asyncio
async def test_ws_handlers_invalid_json(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify dispatch_command handles invalid JSON gracefully."""
    res = await dispatch_command(
        "{invalid-json",
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is False
    assert "Invalid JSON" in res["error"]


@pytest.mark.asyncio
async def test_ws_handlers_get_vehicles(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
    sample_rover_identity: VehicleIdentity,
) -> None:
    """Verify get_vehicles returns active vehicle identities."""
    await vehicle_registry.register(sample_rover_identity)
    cmd = json.dumps({"action": "get_vehicles"})

    res = await dispatch_command(
        cmd,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["system_id"] == 2
    assert res["data"][0]["vehicle_type"] == "rover"


@pytest.mark.asyncio
async def test_ws_handlers_get_parameters(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify get_parameters returns stored parameters for vehicle."""
    param = Parameter("CRUISE_SPD", 1.2, 9, 0)
    await param_store.upsert(2, param)

    cmd = json.dumps({"action": "get_parameters", "system_id": 2})
    res = await dispatch_command(
        cmd,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is True
    assert len(res["data"]) == 1
    assert res["data"][0]["param_id"] == "CRUISE_SPD"


@pytest.mark.asyncio
async def test_ws_handlers_rc_override(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify rc_override dispatches actuator override to AutoConfigEngine."""
    cmd = json.dumps({
        "action": "rc_override",
        "system_id": 2,
        "payload": {"throttle_pwm": 1700, "steering_pwm": 1300},
    })
    res = await dispatch_command(
        cmd,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is True
    mock_auto_config.send_rc_override.assert_awaited_once_with(2, 1700, 1300)


@pytest.mark.asyncio
async def test_ws_handlers_rc_override_drone_4ch(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify rc_override dispatches 4-channel override for drone."""
    cmd = json.dumps({
        "action": "rc_override",
        "system_id": 3,
        "payload": {
            "throttle_pwm": 1650,
            "roll_pwm": 1450,
            "pitch_pwm": 1550,
            "yaw_pwm": 1520,
        },
    })
    res = await dispatch_command(
        cmd,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is True
    assert res["data"]["throttle"] == 1650
    assert res["data"]["roll"] == 1450
    assert res["data"]["pitch"] == 1550
    assert res["data"]["yaw"] == 1520
    mock_auto_config.send_rc_override.assert_awaited_once_with(3, 1650, 1450, 1550, 1520)


@pytest.mark.asyncio
async def test_ws_handlers_set_parameter(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify set_parameter calls AutoConfigEngine.set_parameter."""
    cmd = json.dumps({
        "action": "set_parameter",
        "system_id": 2,
        "payload": {"param_id": "CRUISE_SPD", "value": 2.5},
    })
    res = await dispatch_command(
        cmd,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is True
    mock_auto_config.set_parameter.assert_awaited_once_with(2, "CRUISE_SPD", 2.5)


@pytest.mark.asyncio
async def test_ws_server_broadcast_forwards_telemetry(
    telemetry_bus: TelemetryBus,
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify WebSocketServer broadcasts telemetry bus events to connected clients."""
    server = WebSocketServer(
        telemetry_bus,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    mock_ws = MagicMock()
    mock_ws.send = AsyncMock()

    server._clients.add(mock_ws)
    await server._on_bus_event("telemetry.attitude", {"system_id": 2, "yaw": 0.5})

    assert mock_ws.send.await_count == 1
    sent_data = json.loads(mock_ws.send.call_args[0][0])
    assert sent_data["event"] == "telemetry.attitude"
    assert sent_data["data"]["yaw"] == 0.5


@pytest.mark.asyncio
async def test_http_server_fallback_html(tmp_path: Path) -> None:
    """Verify HttpServer returns fallback HTML when dashboard is not built."""
    server = HttpServer(static_dir=tmp_path)
    req = make_mocked_request("GET", "/", headers={"Host": "localhost"})
    res = await server._handle_request(req)

    assert isinstance(res, web.Response)
    assert res.status == 200
    assert "text/html" in res.content_type
    assert res.text is not None
    assert "Monocranium Core Bridge" in res.text


@pytest.mark.asyncio
async def test_ws_handlers_arm_vehicle(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify arm_vehicle action dispatches arm command."""
    cmd = json.dumps({
        "action": "arm_vehicle",
        "system_id": 3,
        "payload": {"arm": True},
    })
    res = await dispatch_command(
        cmd,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is True
    assert res["data"]["armed"] is True
    mock_auto_config.arm_vehicle.assert_awaited_once_with(3, True)


@pytest.mark.asyncio
async def test_ws_handlers_disarm_vehicle(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify arm_vehicle action dispatches disarm command."""
    cmd = json.dumps({
        "action": "arm_vehicle",
        "system_id": 3,
        "payload": {"arm": False},
    })
    res = await dispatch_command(
        cmd,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is True
    assert res["data"]["armed"] is False
    mock_auto_config.arm_vehicle.assert_awaited_once_with(3, False)


@pytest.mark.asyncio
async def test_ws_handlers_set_flight_mode(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify set_flight_mode action dispatches mode change command."""
    cmd = json.dumps({
        "action": "set_flight_mode",
        "system_id": 3,
        "payload": {"mode": "LOITER"},
    })
    res = await dispatch_command(
        cmd,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is True
    assert res["data"]["mode"] == "LOITER"
    mock_auto_config.set_mode.assert_awaited_once_with(3, "LOITER")


@pytest.mark.asyncio
async def test_ws_handlers_set_flight_mode_defaults(
    vehicle_registry: VehicleRegistry,
    param_store: ParameterStore,
    mock_auto_config: MagicMock,
    mock_conn_manager: MagicMock,
) -> None:
    """Verify set_flight_mode defaults to STABILIZE when mode missing."""
    cmd = json.dumps({
        "action": "set_flight_mode",
        "system_id": 3,
        "payload": {},
    })
    res = await dispatch_command(
        cmd,
        vehicle_registry,
        param_store,
        mock_auto_config,
        mock_conn_manager,
    )
    assert res["success"] is True
    assert res["data"]["mode"] == "STABILIZE"
    mock_auto_config.set_mode.assert_awaited_once_with(3, "STABILIZE")


@pytest.mark.asyncio
async def test_ws_arm_rejection_returns_failure(
    vehicle_registry: VehicleRegistry, param_store: ParameterStore,
    mock_auto_config: MagicMock, mock_conn_manager: MagicMock,
) -> None:
    """An autopilot rejection reaches the browser as an error."""
    mock_auto_config.arm_vehicle.side_effect = ValueError("Vehicle rejected arm")
    result = await dispatch_command(
        json.dumps({"action": "arm_vehicle", "system_id": 3, "payload": {"arm": True}}),
        vehicle_registry, param_store, mock_auto_config, mock_conn_manager,
    )
    assert result["success"] is False
    assert "rejected" in result["error"]


@pytest.mark.asyncio
async def test_ws_mode_timeout_returns_failure(
    vehicle_registry: VehicleRegistry, param_store: ParameterStore,
    mock_auto_config: MagicMock, mock_conn_manager: MagicMock,
) -> None:
    """An unacknowledged mode command cannot be logged as successful."""
    mock_auto_config.set_mode.side_effect = TimeoutError("No COMMAND_ACK")
    result = await dispatch_command(
        json.dumps({"action": "set_flight_mode", "system_id": 3,
                    "payload": {"mode": "LOITER"}}),
        vehicle_registry, param_store, mock_auto_config, mock_conn_manager,
    )
    assert result["success"] is False
    assert "COMMAND_ACK" in result["error"]


@pytest.mark.asyncio
async def test_ws_arm_rejects_string_boolean(
    vehicle_registry: VehicleRegistry, param_store: ParameterStore,
    mock_auto_config: MagicMock, mock_conn_manager: MagicMock,
) -> None:
    """The string 'false' must never arm a vehicle via Python truthiness."""
    result = await dispatch_command(
        json.dumps({"action": "arm_vehicle", "system_id": 3,
                    "payload": {"arm": "false"}}),
        vehicle_registry, param_store, mock_auto_config, mock_conn_manager,
    )
    assert result["success"] is False
    mock_auto_config.arm_vehicle.assert_not_awaited()


@pytest.mark.asyncio
async def test_ws_invalid_system_id_returns_error(
    vehicle_registry: VehicleRegistry, param_store: ParameterStore,
    mock_auto_config: MagicMock, mock_conn_manager: MagicMock,
) -> None:
    """Malformed command targets cannot terminate the WebSocket handler."""
    result = await dispatch_command(
        json.dumps({"action": "arm_vehicle", "system_id": "bad", "payload": {"arm": True}}),
        vehicle_registry, param_store, mock_auto_config, mock_conn_manager,
    )
    assert result["success"] is False
    mock_auto_config.arm_vehicle.assert_not_awaited()

