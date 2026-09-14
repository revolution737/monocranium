from __future__ import annotations

import pytest

from src.simulators.rover_config import (
    DEFAULT_ROVER_CONFIG,
    RoverHardwareConfig,
    build_default_parameter_list,
)


def test_default_config_values() -> None:
    """Verify default rover config physical parameters."""
    cfg = DEFAULT_ROVER_CONFIG
    assert cfg.wheel_diameter_mm == 130.0
    assert cfg.wheel_base_mm == 250.0
    assert cfg.rover_mass_kg == 2.5
    assert cfg.battery_voltage == 11.1
    assert cfg.motor_max_rpm == 6000
    assert cfg.gear_ratio == 30.0


def test_wheel_radius_calculation() -> None:
    """Verify wheel radius calculation converts mm to meters correctly."""
    cfg = RoverHardwareConfig(wheel_diameter_mm=130.0)
    assert cfg.wheel_radius_m == pytest.approx(0.065)


def test_max_wheel_speed_positive() -> None:
    """Verify calculated max wheel speed and angular velocity are positive."""
    cfg = DEFAULT_ROVER_CONFIG
    assert cfg.max_wheel_speed_mps > 0.0
    assert cfg.max_angular_velocity_rps > 0.0
    # At 6000 rpm / 30 = 200 rpm = 3.33 rev/s * 2 * pi * 0.065m ~ 1.36 m/s
    assert cfg.max_wheel_speed_mps == pytest.approx(1.3613, rel=1e-3)


def test_build_default_parameter_list_count() -> None:
    """Verify parameter list generation returns exactly 19 parameters."""
    params = build_default_parameter_list(DEFAULT_ROVER_CONFIG)
    assert len(params) == 19
    param_ids = {p["param_id"] for p in params}
    assert "WHEEL_DIA_MM" in param_ids
    assert "PWM_CENTER" in param_ids
    assert "SYSID_THISMAV" in param_ids
