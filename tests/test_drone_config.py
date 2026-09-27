from __future__ import annotations

import dataclasses

import pytest

from src.simulators.drone_config import (
    DEFAULT_DRONE_CONFIG,
    build_default_drone_parameters,
)


def test_default_drone_config_values() -> None:
    """Verify default quadcopter hardware configuration values."""
    cfg = DEFAULT_DRONE_CONFIG
    assert cfg.mass_kg == 1.5
    assert cfg.motor_kv == 920
    assert cfg.propeller_diameter_inch == 10.0
    assert cfg.battery_voltage == 14.8
    assert cfg.battery_cells == 4
    assert cfg.max_climb_rate_mps == 5.0
    assert cfg.max_descent_rate_mps == 3.0


def test_drone_config_immutability() -> None:
    """Verify DroneHardwareConfig is frozen and immutable."""
    cfg = DEFAULT_DRONE_CONFIG
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.mass_kg = 2.0  # type: ignore[misc]


def test_build_default_drone_parameters() -> None:
    """Verify drone parameter list contains 18 ArduPilot Copter parameters."""
    params = build_default_drone_parameters(DEFAULT_DRONE_CONFIG)
    assert len(params) == 18
    param_ids = {p["param_id"] for p in params}
    assert "SYSID_THISMAV" in param_ids
    assert "FRAME_CLASS" in param_ids
    assert "FRAME_TYPE" in param_ids
    assert "PILOT_SPEED_UP" in param_ids
    assert "ANGLE_MAX" in param_ids
    assert "ATC_ANG_RLL_P" in param_ids
    assert "BATT_VOLT" in param_ids

    sysid_param = next(p for p in params if p["param_id"] == "SYSID_THISMAV")
    assert sysid_param["value"] == 3.0
