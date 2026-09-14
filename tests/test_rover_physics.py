from __future__ import annotations

import pytest

from src.core.types import AttitudeData, GpsData
from src.simulators.rover_config import DEFAULT_ROVER_CONFIG
from src.simulators.rover_physics import RoverKinematics


def test_initial_position() -> None:
    """Verify default initial position is (400.0, 300.0)."""
    rover = RoverKinematics(DEFAULT_ROVER_CONFIG)
    assert rover.position == (400.0, 300.0)
    assert rover.heading_rad == 0.0
    assert rover.speed_mps == 0.0


def test_stationary_at_center_pwm() -> None:
    """Verify neutral PWM (1500, 1500) results in zero motion."""
    rover = RoverKinematics(DEFAULT_ROVER_CONFIG)
    rover.update(1500, 1500, dt=0.1)
    assert rover.speed_mps == 0.0
    assert rover.position == (400.0, 300.0)


def test_forward_movement() -> None:
    """Verify maximum throttle produces forward motion along heading vector."""
    rover = RoverKinematics(DEFAULT_ROVER_CONFIG)
    rover.update(2000, 1500, dt=1.0)
    x, y = rover.position
    assert x > 400.0
    assert y == pytest.approx(300.0)
    assert rover.speed_mps > 0.0


def test_reverse_movement() -> None:
    """Verify minimum throttle produces backward motion."""
    rover = RoverKinematics(DEFAULT_ROVER_CONFIG)
    rover.update(1000, 1500, dt=1.0)
    x, y = rover.position
    assert x < 400.0
    assert y == pytest.approx(300.0)
    assert rover.speed_mps < 0.0


def test_turn_in_place() -> None:
    """Verify steering without throttle rotates rover with minimal translation."""
    rover = RoverKinematics(DEFAULT_ROVER_CONFIG)
    rover.update(1500, 2000, dt=1.0)
    assert rover.heading_rad != 0.0
    assert rover.angular_velocity_rps != 0.0
    assert rover.speed_mps == pytest.approx(0.0)
    assert rover.position == (400.0, 300.0)


def test_deadzone_no_movement() -> None:
    """Verify PWM inputs within deadzone are clamped to neutral."""
    rover = RoverKinematics(DEFAULT_ROVER_CONFIG)
    # 1520 is within 1500 ± 50 deadzone
    rover.update(1520, 1500, dt=1.0)
    assert rover.speed_mps == 0.0
    assert rover.position == (400.0, 300.0)


def test_gps_data_returns_gps_data_type() -> None:
    """Verify gps_data returns a valid GpsData instance."""
    rover = RoverKinematics(DEFAULT_ROVER_CONFIG)
    gps = rover.gps_data
    assert isinstance(gps, GpsData)
    assert gps.lat > 0.0
    assert gps.lon > 0.0
    assert gps.satellites == 12

    att = rover.attitude_data
    assert isinstance(att, AttitudeData)
    assert att.yaw == 0.0


def test_reset() -> None:
    """Verify reset restores starting coordinates and zero velocity."""
    rover = RoverKinematics(DEFAULT_ROVER_CONFIG, start_x=100.0, start_y=200.0)
    rover.update(1800, 1700, dt=2.0)
    assert rover.position != (100.0, 200.0)
    assert rover.heading_rad != 0.0

    rover.reset()
    assert rover.position == (100.0, 200.0)
    assert rover.heading_rad == 0.0
    assert rover.speed_mps == 0.0
