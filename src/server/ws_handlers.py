from __future__ import annotations

import json
import logging
from typing import Any

from src.core.auto_config import AutoConfigEngine
from src.core.connection import ConnectionManager
from src.core.parameter_store import ParameterStore
from src.core.types import ConnectionEndpoint
from src.core.vehicle_registry import VehicleRegistry

logger = logging.getLogger(__name__)


async def dispatch_command(
    raw_msg: str,
    registry: VehicleRegistry,
    param_store: ParameterStore,
    auto_config: AutoConfigEngine,
    conn_mgr: ConnectionManager,
) -> dict[str, Any]:
    """Parse and route client WebSocket command to system services.

    Args:
        raw_msg: Incoming JSON command string.
        registry: VehicleRegistry instance.
        param_store: ParameterStore instance.
        auto_config: AutoConfigEngine instance.
        conn_mgr: ConnectionManager instance.

    Returns:
        Structured response dictionary.
    """
    try:
        data = json.loads(raw_msg)
    except json.JSONDecodeError as e:
        return {"response_to": "unknown", "success": False, "error": f"Invalid JSON: {e}"}

    action = data.get("action")
    if not action or not isinstance(action, str):
        return {"response_to": "unknown", "success": False, "error": "Missing 'action' field"}

    sys_id = int(data.get("system_id", 0))
    payload = data.get("payload", {})

    return await _execute_action(
        action,
        sys_id,
        payload,
        registry,
        param_store,
        auto_config,
        conn_mgr,
    )


async def _dispatch_query_action(
    action: str,
    sys_id: int,
    registry: VehicleRegistry,
    param_store: ParameterStore,
    conn_mgr: ConnectionManager,
) -> dict[str, Any] | None:
    """Handle query/read actions returning system state."""
    if action == "get_vehicles":
        vehicles = [v.to_dict() for v in registry.list_all()]
        return {"response_to": action, "success": True, "data": vehicles}
    if action == "get_parameters":
        params = [p.to_dict() for p in param_store.get_all(sys_id)]
        return {"response_to": action, "success": True, "data": params}
    if action == "get_connection_status":
        statuses = [
            {"address": c.endpoint.address, "port": c.endpoint.port, "state": c.state.value}
            for c in conn_mgr.list_connections()
        ]
        return {"response_to": action, "success": True, "data": statuses}
    return None


async def _dispatch_command_action(
    action: str,
    sys_id: int,
    payload: dict[str, Any],
    auto_config: AutoConfigEngine,
    conn_mgr: ConnectionManager,
) -> dict[str, Any] | None:
    """Handle command/control actions dispatched to AutoConfigEngine."""
    if action == "set_parameter":
        param_id = str(payload.get("param_id", ""))
        val = float(payload.get("value", 0.0))
        await auto_config.set_parameter(sys_id, param_id, val)
        res_data = {"param_id": param_id, "value": val}
        return {"response_to": action, "success": True, "data": res_data}
    if action == "rc_override":
        rc_data = await _handle_rc_override(sys_id, payload, auto_config)
        return {"response_to": action, "success": True, "data": rc_data}
    if action == "run_autoconfig":
        discovered = await _handle_run_autoconfig(payload, auto_config, conn_mgr)
        return {"response_to": action, "success": True, "data": discovered}
    if action == "arm_vehicle":
        arm_data = await _handle_arm_vehicle(sys_id, payload, auto_config)
        return {"response_to": action, "success": True, "data": arm_data}
    if action == "set_flight_mode":
        mode_data = await _handle_set_flight_mode(sys_id, payload, auto_config)
        return {"response_to": action, "success": True, "data": mode_data}
    return None


async def _execute_action(
    action: str,
    sys_id: int,
    payload: dict[str, Any],
    registry: VehicleRegistry,
    param_store: ParameterStore,
    auto_config: AutoConfigEngine,
    conn_mgr: ConnectionManager,
) -> dict[str, Any]:
    """Execute action and return standard response."""
    try:
        query_res = await _dispatch_query_action(action, sys_id, registry, param_store, conn_mgr)
        if query_res is not None:
            return query_res

        cmd_res = await _dispatch_command_action(action, sys_id, payload, auto_config, conn_mgr)
        if cmd_res is not None:
            return cmd_res

        return {"response_to": action, "success": False, "error": f"Unknown action '{action}'"}
    except (ValueError, KeyError, OSError) as e:
        logger.error("Action '%s' execution failed: %s", action, e)
        return {"response_to": action, "success": False, "error": str(e)}


async def _handle_rc_override(
    sys_id: int,
    payload: dict[str, Any],
    auto_config: AutoConfigEngine,
) -> dict[str, Any]:
    """Parse and dispatch 2-axis or 4-axis RC override commands."""
    throttle = int(payload.get("throttle_pwm", 1500))
    steering = int(payload.get("roll_pwm", payload.get("steering_pwm", 1500)))
    pitch = int(payload.get("pitch_pwm", 0))
    yaw = int(payload.get("yaw_pwm", 0))

    if pitch == 0 and yaw == 0:
        await auto_config.send_rc_override(sys_id, throttle, steering)
    else:
        await auto_config.send_rc_override(sys_id, throttle, steering, pitch, yaw)

    return {
        "throttle": throttle,
        "steering": steering,
        "roll": steering,
        "pitch": pitch,
        "yaw": yaw,
    }


async def _handle_run_autoconfig(
    payload: dict[str, Any],
    auto_config: AutoConfigEngine,
    conn_mgr: ConnectionManager,
) -> list[dict[str, Any]]:
    """Helper to run scan across target or default endpoints."""
    raw_eps = payload.get("endpoints")
    if raw_eps and isinstance(raw_eps, list):
        endpoints = [
            ConnectionEndpoint(
                address=ep.get("address", "127.0.0.1"),
                port=int(ep.get("port", 5770)),
                protocol=ep.get("protocol", "tcp"),
            )
            for ep in raw_eps
        ]
    else:
        endpoints = [c.endpoint for c in conn_mgr.list_connections()]

    discovered = await auto_config.run_full_scan(endpoints)
    return [v.to_dict() for v in discovered]


async def _handle_arm_vehicle(
    sys_id: int,
    payload: dict[str, Any],
    auto_config: AutoConfigEngine,
) -> dict[str, Any]:
    """Parse and dispatch arm or disarm command."""
    arm = bool(payload.get("arm", False))
    await auto_config.arm_vehicle(sys_id, arm)
    return {"system_id": sys_id, "armed": arm}


async def _handle_set_flight_mode(
    sys_id: int,
    payload: dict[str, Any],
    auto_config: AutoConfigEngine,
) -> dict[str, Any]:
    """Parse and dispatch flight mode change command."""
    mode = str(payload.get("mode", "STABILIZE"))
    await auto_config.set_mode(sys_id, mode)
    return {"system_id": sys_id, "mode": mode}

