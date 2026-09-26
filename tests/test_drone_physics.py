from __future__ import annotations

import pytest

from src.core.types import AttitudeData, GpsData
from src.simulators.drone_config import DEFAULT_DRONE_CONFIG
from src.simulators.drone_physics import DroneKinematics


def test_drone_initial_state() -> None:
    """Verify quadcopter starts stationary at ground level."""
    drone = DroneKinematics(DEFAULT_DRONE_CONFIG)
    assert drone.altitude_m == 0.0
    assert drone.climb_rate_mps == 0.0
    assert drone.speed_mps == 0.0
    att = drone.attitude_data
    assert isinstance(att, AttitudeData)
    assert att.roll == 0.0
    assert att.pitch == 0.0
    assert att.yaw == 0.0


def test_drone_hover_throttle() -> None:
    """Verify neutral throttle (1500) results in zero vertical climb."""
    drone = DroneKinematics(DEFAULT_DRONE_CONFIG)
    drone.update(throttle_pwm=1500, roll_pwm=1500, pitch_pwm=1500, yaw_pwm=1500, dt=1.0)
    assert drone.climb_rate_mps == 0.0
    assert drone.altitude_m == 0.0


def test_drone_climb() -> None:
    """Verify positive throttle (2000) causes ascent."""
    drone = DroneKinematics(DEFAULT_DRONE_CONFIG)
    drone.update(throttle_pwm=2000, roll_pwm=1500, pitch_pwm=1500, yaw_pwm=1500, dt=2.0)
    assert drone.climb_rate_mps > 0.0
    assert drone.altitude_m == pytest.approx(10.0)  # 5.0 m/s * 2.0 s = 10.0 m


def test_drone_descent_ground_clamped() -> None:
    """Verify descent does not allow negative altitude below ground."""
    drone = DroneKinematics(DEFAULT_DRONE_CONFIG)
    drone.update(throttle_pwm=1000, roll_pwm=1500, pitch_pwm=1500, yaw_pwm=1500, dt=1.0)
    assert drone.altitude_m == 0.0
    assert drone.climb_rate_mps >= 0.0


def test_drone_attitude_angles() -> None:
    """Verify roll and pitch stick inputs generate tilt angles."""
    drone = DroneKinematics(DEFAULT_DRONE_CONFIG)
    drone.update(throttle_pwm=1700, roll_pwm=2000, pitch_pwm=2000, yaw_pwm=1500, dt=0.5)
    att = drone.attitude_data
    assert att.roll > 0.0
    assert att.pitch < 0.0


def test_drone_yaw_rotation() -> None:
    """Verify yaw stick input rotates heading."""
    drone = DroneKinematics(DEFAULT_DRONE_CONFIG)
    drone.update(throttle_pwm=1700, roll_pwm=1500, pitch_pwm=1500, yaw_pwm=2000, dt=1.0)
    assert drone.attitude_data.yaw > 0.0


def test_drone_gps_data() -> None:
    """Verify gps_data accurately reflects altitude and 3D fix."""
    drone = DroneKinematics(DEFAULT_DRONE_CONFIG)
    drone.update(throttle_pwm=2000, roll_pwm=1500, pitch_pwm=1500, yaw_pwm=1500, dt=1.0)
    gps = drone.gps_data
    assert isinstance(gps, GpsData)
    assert gps.alt == pytest.approx(5.0)
    assert gps.fix_type == 3
    assert gps.satellites == 12


def test_drone_reset() -> None:
    """Verify reset returns state to origin at ground level."""
    drone = DroneKinematics(DEFAULT_DRONE_CONFIG)
    drone.update(throttle_pwm=2000, roll_pwm=1800, pitch_pwm=1800, yaw_pwm=1800, dt=2.0)
    drone.reset()
    assert drone.altitude_m == 0.0
    assert drone.climb_rate_mps == 0.0
    assert drone.speed_mps == 0.0
