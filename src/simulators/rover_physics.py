from __future__ import annotations

import logging
import math

from src.core.types import AttitudeData, GpsData
from src.simulators.rover_config import RoverHardwareConfig

logger = logging.getLogger(__name__)

PIXELS_PER_METER: int = 100
GPS_ORIGIN_LAT: float = 28.6139
GPS_ORIGIN_LON: float = 77.2090
LAT_PER_METER: float = 1.0 / 111_320.0
LON_PER_METER: float = 1.0 / 78_710.0


class RoverKinematics:
    """Differential-drive (skid-steer) kinematics simulator for 4WD rover."""

    def __init__(
        self,
        config: RoverHardwareConfig,
        start_x: float = 400.0,
        start_y: float = 300.0,
    ) -> None:
        """Initialise rover kinematics at initial pixel position.

        Args:
            config: Rover hardware parameters.
            start_x: Initial horizontal pixel coordinate.
            start_y: Initial vertical pixel coordinate.
        """
        self._config = config
        self._start_x = start_x
        self._start_y = start_y
        self._x = start_x
        self._y = start_y
        self._heading = 0.0
        self._speed = 0.0
        self._angular_velocity = 0.0

    @staticmethod
    def _normalise_pwm(pwm: int, cfg: RoverHardwareConfig) -> float:
        """Normalise a PWM value to the range [-1.0, +1.0], applying deadzone.

        Args:
            pwm: Raw PWM value (1000-2000).
            cfg: Rover hardware configuration.

        Returns:
            Normalised value in [-1.0, +1.0]. Returns 0.0 if in deadzone.
        """
        deviation = pwm - cfg.pwm_center
        if abs(deviation) <= cfg.pwm_deadzone:
            return 0.0
        half_range = (cfg.pwm_max - cfg.pwm_min) / 2.0
        return max(-1.0, min(1.0, deviation / half_range))

    def update(self, throttle_pwm: int, steering_pwm: int, dt: float) -> None:
        """Update rover position and heading based on PWM inputs.

        Args:
            throttle_pwm: Throttle PWM value (1000-2000, center=1500).
            steering_pwm: Steering PWM value (1000-2000, center=1500).
            dt: Time step in seconds.
        """
        cfg = self._config
        throttle_norm = self._normalise_pwm(throttle_pwm, cfg)
        steering_norm = self._normalise_pwm(steering_pwm, cfg)

        v_left_norm = max(-1.0, min(1.0, throttle_norm + steering_norm))
        v_right_norm = max(-1.0, min(1.0, throttle_norm - steering_norm))

        v_left = v_left_norm * cfg.max_wheel_speed_mps
        v_right = v_right_norm * cfg.max_wheel_speed_mps

        self._speed = (v_right + v_left) / 2.0
        self._angular_velocity = (v_right - v_left) / cfg.wheel_base_m

        self._heading += self._angular_velocity * dt
        self._x += self._speed * math.cos(self._heading) * dt * PIXELS_PER_METER
        self._y += self._speed * math.sin(self._heading) * dt * PIXELS_PER_METER

    @property
    def position(self) -> tuple[float, float]:
        """Current pixel coordinates (x, y)."""
        return (self._x, self._y)

    @property
    def heading_rad(self) -> float:
        """Current heading angle in radians (0 = east/right)."""
        return self._heading

    @property
    def heading_deg(self) -> float:
        """Current heading angle in degrees."""
        return math.degrees(self._heading)

    @property
    def speed_mps(self) -> float:
        """Current linear velocity in meters per second."""
        return self._speed

    @property
    def angular_velocity_rps(self) -> float:
        """Current rotational velocity in radians per second."""
        return self._angular_velocity

    @property
    def gps_data(self) -> GpsData:
        """Convert pixel position to simulated GPS coordinates."""
        meters_x = self._x / PIXELS_PER_METER
        meters_y = self._y / PIXELS_PER_METER
        lat = GPS_ORIGIN_LAT + (meters_y * LAT_PER_METER)
        lon = GPS_ORIGIN_LON + (meters_x * LON_PER_METER)
        return GpsData(lat=lat, lon=lon, alt=0.0, fix_type=3, satellites=12)

    @property
    def attitude_data(self) -> AttitudeData:
        """Current attitude data with yaw equal to rover heading."""
        return AttitudeData(roll=0.0, pitch=0.0, yaw=self._heading)

    def reset(self) -> None:
        """Reset kinematics state to starting position and orientation."""
        self._x = self._start_x
        self._y = self._start_y
        self._heading = 0.0
        self._speed = 0.0
        self._angular_velocity = 0.0
