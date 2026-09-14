from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class RoverHardwareConfig:
    """Physical parameters for the simulated 4WD skid-steer rover.

    Default values model a hobby-grade rover with:
    - 130mm rubber wheels
    - 775 DC brushed motors with 30:1 gearbox
    - 3S LiPo battery (11.1V, 5000mAh)
    """

    # Chassis
    wheel_diameter_mm: float = 130.0
    wheel_base_mm: float = 250.0
    track_length_mm: float = 300.0
    rover_mass_kg: float = 2.5

    # Motors
    motor_max_rpm: int = 6000
    motor_stall_torque_nm: float = 0.8
    gear_ratio: float = 30.0
    motor_count: int = 4

    # Electrical
    battery_voltage: float = 11.1
    battery_capacity_mah: int = 5000
    battery_cells: int = 3

    # PWM Ranges
    pwm_min: int = 1000
    pwm_max: int = 2000
    pwm_center: int = 1500
    pwm_deadzone: int = 50

    @property
    def wheel_radius_m(self) -> float:
        """Wheel radius in meters."""
        return (self.wheel_diameter_mm / 2.0) / 1000.0

    @property
    def wheel_base_m(self) -> float:
        """Distance between left and right wheel centers in meters."""
        return self.wheel_base_mm / 1000.0

    @property
    def max_wheel_speed_mps(self) -> float:
        """Maximum linear speed at the wheel surface after gear reduction, in m/s."""
        output_rpm = self.motor_max_rpm / self.gear_ratio
        return (output_rpm / 60.0) * 2.0 * math.pi * self.wheel_radius_m

    @property
    def max_angular_velocity_rps(self) -> float:
        """Maximum angular velocity when spinning in place, in rad/s."""
        return (2.0 * self.max_wheel_speed_mps) / self.wheel_base_m


DEFAULT_ROVER_CONFIG = RoverHardwareConfig()


def _make_param(param_id: str, value: float, param_type: int, index: int) -> dict[str, Any]:
    """Helper to construct a parameter dict cleanly."""
    return {
        "param_id": param_id,
        "value": value,
        "param_type": param_type,
        "param_index": index,
    }


def build_default_parameter_list(config: RoverHardwareConfig) -> list[dict[str, Any]]:
    """Build the list of MAVLink parameters from a hardware config.

    Returns a list of dicts with keys: param_id, value, param_type, param_index.
    param_type 9 = REAL32 (float), param_type 6 = INT32.

    Args:
        config: RoverHardwareConfig specifying physical parameters.

    Returns:
        List of 19 MAVLink parameter dictionaries.
    """
    return [
        _make_param("SYSID_THISMAV", 2.0, 6, 0),
        _make_param("WHEEL_DIA_MM", config.wheel_diameter_mm, 9, 1),
        _make_param("WHEEL_BASE_MM", config.wheel_base_mm, 9, 2),
        _make_param("TRACK_LEN_MM", config.track_length_mm, 9, 3),
        _make_param("MASS_KG", config.rover_mass_kg, 9, 4),
        _make_param("MOT_MAX_RPM", float(config.motor_max_rpm), 9, 5),
        _make_param("MOT_STALL_TQ", config.motor_stall_torque_nm, 9, 6),
        _make_param("GEAR_RATIO", config.gear_ratio, 9, 7),
        _make_param("MOT_COUNT", float(config.motor_count), 6, 8),
        _make_param("BATT_VOLT", config.battery_voltage, 9, 9),
        _make_param("BATT_CAP_MAH", float(config.battery_capacity_mah), 9, 10),
        _make_param("BATT_CELLS", float(config.battery_cells), 6, 11),
        _make_param("PWM_MIN", float(config.pwm_min), 6, 12),
        _make_param("PWM_MAX", float(config.pwm_max), 6, 13),
        _make_param("PWM_CENTER", float(config.pwm_center), 6, 14),
        _make_param("PWM_DEADZONE", float(config.pwm_deadzone), 6, 15),
        _make_param("CRUISE_SPEED", 1.0, 9, 16),
        _make_param("FS_ACTION", 1.0, 6, 17),
        _make_param("FRAME_TYPE", 1.0, 6, 18),
    ]
