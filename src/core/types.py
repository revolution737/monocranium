from __future__ import annotations

import enum
import logging
from dataclasses import asdict, dataclass
from typing import Any, TypedDict

logger = logging.getLogger(__name__)


class VehicleType(enum.Enum):
    """Type of unmanned vehicle."""

    ROVER = "rover"
    UNKNOWN = "unknown"

    @classmethod
    def from_mav_type(cls, mav_type: int) -> VehicleType:
        """Convert a MAVLink MAV_TYPE integer to a VehicleType.

        Args:
            mav_type: Integer from the MAVLink HEARTBEAT message 'type' field.

        Returns:
            VehicleType.ROVER if mav_type == 10, otherwise VehicleType.UNKNOWN.
        """
        mav_type_ground_rover = 10
        if mav_type == mav_type_ground_rover:
            return cls.ROVER
        return cls.UNKNOWN


class AutopilotType(enum.Enum):
    """Type of autopilot firmware."""

    ARDUPILOT = "ardupilot"
    GENERIC = "generic"
    UNKNOWN = "unknown"

    @classmethod
    def from_mav_autopilot(cls, mav_autopilot: int) -> AutopilotType:
        """Convert a MAVLink MAV_AUTOPILOT integer to an AutopilotType.

        Args:
            mav_autopilot: Integer from the MAVLink HEARTBEAT message 'autopilot' field.

        Returns:
            The corresponding AutopilotType enum member.
        """
        mav_autopilot_ardupilotmega = 3
        mav_autopilot_generic = 0
        if mav_autopilot == mav_autopilot_ardupilotmega:
            return cls.ARDUPILOT
        if mav_autopilot == mav_autopilot_generic:
            return cls.GENERIC
        return cls.UNKNOWN


class ConnectionState(enum.Enum):
    """State of a MAVLink connection."""

    DISCONNECTED = "disconnected"
    CONNECTING = "connecting"
    CONNECTED = "connected"
    HEARTBEAT_LOST = "heartbeat_lost"


@dataclass(frozen=True)
class AttitudeData:
    """Vehicle attitude in radians."""

    roll: float
    pitch: float
    yaw: float

    def to_dict(self) -> dict[str, float]:
        """Return a JSON-serialisable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class GpsData:
    """Vehicle GPS coordinates and status."""

    lat: float
    lon: float
    alt: float
    fix_type: int
    satellites: int

    def to_dict(self) -> dict[str, float | int]:
        """Return a JSON-serialisable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class BatteryData:
    """Vehicle battery status."""

    voltage: float
    current: float
    remaining: int

    def to_dict(self) -> dict[str, float | int]:
        """Return a JSON-serialisable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class ConnectionEndpoint:
    """MAVLink communication endpoint."""

    address: str
    port: int
    protocol: str

    def to_dict(self) -> dict[str, str | int]:
        """Return a JSON-serialisable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class Parameter:
    """Individual vehicle parameter."""

    param_id: str
    value: float
    param_type: int
    param_index: int

    def to_dict(self) -> dict[str, str | float | int]:
        """Return a JSON-serialisable dictionary."""
        return asdict(self)


@dataclass(frozen=True)
class VehicleIdentity:
    """Unique identity and firmware details of a connected vehicle."""

    system_id: int
    component_id: int
    vehicle_type: VehicleType
    autopilot_type: AutopilotType
    firmware_version: str

    def to_dict(self) -> dict[str, str | int]:
        """Return a JSON-serialisable dictionary with enums converted to strings."""
        return {
            "system_id": self.system_id,
            "component_id": self.component_id,
            "vehicle_type": self.vehicle_type.value,
            "autopilot_type": self.autopilot_type.value,
            "firmware_version": self.firmware_version,
        }


@dataclass(frozen=True)
class TelemetrySnapshot:
    """Unified telemetry snapshot at a given timestamp."""

    timestamp: float
    attitude: AttitudeData
    gps: GpsData
    battery: BatteryData
    rc_channels: list[int]

    def to_dict(self) -> dict[str, object]:
        """Return a JSON-serialisable dictionary handling nested dataclasses."""
        return {
            "timestamp": self.timestamp,
            "attitude": self.attitude.to_dict(),
            "gps": self.gps.to_dict(),
            "battery": self.battery.to_dict(),
            "rc_channels": list(self.rc_channels),
        }


class BridgeCommand(TypedDict):
    """A command sent from WebSocket client to the Core Bridge."""

    action: str
    target_system_id: int
    payload: dict[str, Any]
