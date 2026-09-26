from __future__ import annotations

import logging
import math

from src.core.types import AttitudeData, GpsData
from src.simulators.drone_config import DroneHardwareConfig

logger = logging.getLogger(__name__)

GPS_ORIGIN_LAT: float = 28.6139
GPS_ORIGIN_LON: float = 77.2090
LAT_PER_METER: float = 1.0 / 111_320.0
LON_PER_METER: float = 1.0 / 78_710.0
MIN_FLIGHT_ALT_M: float = 0.05
MAX_HORIZONTAL_SPEED_MPS: float = 12.0
GPS_FIX_3D: int = 3
GPS_SATELLITES: int = 12


class DroneKinematics:
    """Kinematic flight physics model for simulated ArduPilot quadcopter."""

    def __init__(
        self,
        config: DroneHardwareConfig,
        origin_lat: float = GPS_ORIGIN_LAT,
        origin_lon: float = GPS_ORIGIN_LON,
    ) -> None:
        """Initialise quadcopter kinematics at ground level."""
        self._config = config
        self._origin_lat = origin_lat
        self._origin_lon = origin_lon
        self._x: float = 0.0
        self._y: float = 0.0
        self._altitude: float = 0.0
        self._climb_rate: float = 0.0
        self._roll: float = 0.0
        self._pitch: float = 0.0
        self._yaw: float = 0.0
        self._speed: float = 0.0

    @staticmethod
    def _normalise_axis(pwm: int, cfg: DroneHardwareConfig) -> float:
        """Normalise PWM input to range [-1.0, +1.0] with deadband filtering."""
        deviation = pwm - cfg.pwm_center
        if abs(deviation) <= cfg.pwm_deadzone:
            return 0.0
        half_range = (cfg.pwm_max - cfg.pwm_min) / 2.0
        return max(-1.0, min(1.0, deviation / half_range))

    def _update_altitude(self, throttle_norm: float, dt: float) -> None:
        """Update vertical velocity and altitude position."""
        cfg = self._config
        if throttle_norm > 0:
            self._climb_rate = throttle_norm * cfg.max_climb_rate_mps
        elif throttle_norm < 0:
            self._climb_rate = throttle_norm * cfg.max_descent_rate_mps
        else:
            self._climb_rate = 0.0

        self._altitude = max(0.0, self._altitude + (self._climb_rate * dt))
        if self._altitude <= 0.0:
            self._climb_rate = max(0.0, self._climb_rate)

    def _update_attitude_and_motion(
        self,
        roll_norm: float,
        pitch_norm: float,
        yaw_norm: float,
        dt: float,
    ) -> None:
        """Update roll, pitch, yaw, and compute horizontal translation."""
        max_tilt_rad = math.radians(self._config.max_tilt_deg)
        self._roll = roll_norm * max_tilt_rad
        self._pitch = -pitch_norm * max_tilt_rad

        yaw_rate_rad = math.radians(self._config.max_yaw_rate_deg_s) * yaw_norm
        self._yaw = (self._yaw + yaw_rate_rad * dt) % (2.0 * math.pi)

        if self._altitude > MIN_FLIGHT_ALT_M:
            vx_body = pitch_norm * MAX_HORIZONTAL_SPEED_MPS
            vy_body = roll_norm * MAX_HORIZONTAL_SPEED_MPS
            self._x += (vx_body * math.cos(self._yaw) - vy_body * math.sin(self._yaw)) * dt
            self._y += (vx_body * math.sin(self._yaw) + vy_body * math.cos(self._yaw)) * dt
            self._speed = math.hypot(vx_body, vy_body)
        else:
            self._speed = 0.0

    def update(
        self,
        throttle_pwm: int,
        roll_pwm: int,
        pitch_pwm: int,
        yaw_pwm: int,
        dt: float,
    ) -> None:
        """Update quadcopter state from 4-axis PWM inputs."""
        cfg = self._config
        thr_norm = self._normalise_axis(throttle_pwm, cfg)
        roll_norm = self._normalise_axis(roll_pwm, cfg)
        pitch_norm = self._normalise_axis(pitch_pwm, cfg)
        yaw_norm = self._normalise_axis(yaw_pwm, cfg)

        self._update_altitude(thr_norm, dt)
        self._update_attitude_and_motion(roll_norm, pitch_norm, yaw_norm, dt)

    @property
    def altitude_m(self) -> float:
        """Altitude above ground in meters."""
        return self._altitude

    @property
    def climb_rate_mps(self) -> float:
        """Vertical climb velocity in meters per second."""
        return self._climb_rate

    @property
    def speed_mps(self) -> float:
        """Horizontal velocity magnitude in meters per second."""
        return self._speed

    @property
    def attitude_data(self) -> AttitudeData:
        """Current 3-axis Euler attitude in radians."""
        return AttitudeData(roll=self._roll, pitch=self._pitch, yaw=self._yaw)

    @property
    def gps_data(self) -> GpsData:
        """Simulated GPS coordinates including MSL altitude."""
        lat = self._origin_lat + (self._y * LAT_PER_METER)
        lon = self._origin_lon + (self._x * LON_PER_METER)
        return GpsData(
            lat=lat,
            lon=lon,
            alt=self._altitude,
            fix_type=GPS_FIX_3D,
            satellites=GPS_SATELLITES,
        )

    def reset(self) -> None:
        """Reset flight state to ground level origin."""
        self._x = 0.0
        self._y = 0.0
        self._altitude = 0.0
        self._climb_rate = 0.0
        self._roll = 0.0
        self._pitch = 0.0
        self._yaw = 0.0
        self._speed = 0.0
