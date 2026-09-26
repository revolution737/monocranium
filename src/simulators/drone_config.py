from __future__ import annotations

from dataclasses import dataclass
from typing import Any

PARAM_TYPE_INT32: int = 6
PARAM_TYPE_REAL32: int = 9


@dataclass(frozen=True)
class DroneHardwareConfig:
    """Physical and operational configuration for simulated ArduPilot quadcopter.

    Models a standard 450mm quadcopter with:
    - 4x 920KV brushless motors with 1045 propellers
    - 4S LiPo battery (14.8V, 4000mAh)
    - Default hover throttle at mid-stick (1500 PWM)
    """

    mass_kg: float = 1.5
    motor_kv: int = 920
    propeller_diameter_inch: float = 10.0
    battery_voltage: float = 14.8
    battery_capacity_mah: int = 4000
    battery_cells: int = 4

    max_climb_rate_mps: float = 5.0
    max_descent_rate_mps: float = 3.0
    max_tilt_deg: float = 35.0
    max_yaw_rate_deg_s: float = 180.0

    pwm_min: int = 1000
    pwm_max: int = 2000
    pwm_center: int = 1500
    pwm_deadzone: int = 50


DEFAULT_DRONE_CONFIG = DroneHardwareConfig()


def _make_param(param_id: str, value: float, param_type: int, index: int) -> dict[str, Any]:
    """Construct an individual parameter entry."""
    return {
        "param_id": param_id,
        "value": value,
        "param_type": param_type,
        "param_index": index,
    }


def build_default_drone_parameters(config: DroneHardwareConfig) -> list[dict[str, Any]]:
    """Generate default ArduPilot Copter parameter dictionary list.

    Args:
        config: Hardware configuration defining physical constants.

    Returns:
        List of 18 MAVLink parameter dictionaries.
    """
    return [
        _make_param("SYSID_THISMAV", 3.0, PARAM_TYPE_INT32, 0),
        _make_param("FRAME_CLASS", 1.0, PARAM_TYPE_INT32, 1),
        _make_param("FRAME_TYPE", 1.0, PARAM_TYPE_INT32, 2),
        _make_param("PILOT_SPEED_UP", config.max_climb_rate_mps * 100.0, PARAM_TYPE_REAL32, 3),
        _make_param("PILOT_SPEED_DN", config.max_descent_rate_mps * 100.0, PARAM_TYPE_REAL32, 4),
        _make_param("ANGLE_MAX", config.max_tilt_deg * 100.0, PARAM_TYPE_REAL32, 5),
        _make_param("ATC_ANG_RLL_P", 4.5, PARAM_TYPE_REAL32, 6),
        _make_param("ATC_ANG_PIT_P", 4.5, PARAM_TYPE_REAL32, 7),
        _make_param("ATC_ANG_YAW_P", 4.5, PARAM_TYPE_REAL32, 8),
        _make_param("MOT_KV", float(config.motor_kv), PARAM_TYPE_REAL32, 9),
        _make_param("PROP_DIA_INCH", config.propeller_diameter_inch, PARAM_TYPE_REAL32, 10),
        _make_param("BATT_VOLT", config.battery_voltage, PARAM_TYPE_REAL32, 11),
        _make_param("BATT_CAP_MAH", float(config.battery_capacity_mah), PARAM_TYPE_REAL32, 12),
        _make_param("BATT_CELLS", float(config.battery_cells), PARAM_TYPE_INT32, 13),
        _make_param("PWM_MIN", float(config.pwm_min), PARAM_TYPE_INT32, 14),
        _make_param("PWM_MAX", float(config.pwm_max), PARAM_TYPE_INT32, 15),
        _make_param("PWM_CENTER", float(config.pwm_center), PARAM_TYPE_INT32, 16),
        _make_param("PWM_DEADZONE", float(config.pwm_deadzone), PARAM_TYPE_INT32, 17),
    ]
