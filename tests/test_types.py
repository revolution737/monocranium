from __future__ import annotations

from dataclasses import FrozenInstanceError

import pytest

from src.core.types import (
    AttitudeData,
    AutopilotType,
    BatteryData,
    GpsData,
    Parameter,
    TelemetrySnapshot,
    VehicleIdentity,
    VehicleType,
)


def test_vehicle_type_from_mav_type_rover() -> None:
    """Verify VehicleType.from_mav_type maps 10 to ROVER."""
    assert VehicleType.from_mav_type(10) == VehicleType.ROVER


def test_vehicle_type_from_mav_type_copter() -> None:
    """Verify VehicleType.from_mav_type maps multirotor types to COPTER."""
    assert VehicleType.from_mav_type(2) == VehicleType.COPTER
    assert VehicleType.from_mav_type(3) == VehicleType.COPTER
    assert VehicleType.from_mav_type(4) == VehicleType.COPTER
    assert VehicleType.from_mav_type(13) == VehicleType.COPTER
    assert VehicleType.from_mav_type(14) == VehicleType.COPTER
    assert VehicleType.from_mav_type(15) == VehicleType.COPTER


def test_vehicle_type_from_mav_type_unknown() -> None:
    """Verify VehicleType.from_mav_type maps unsupported values to UNKNOWN."""
    assert VehicleType.from_mav_type(999) == VehicleType.UNKNOWN


def test_autopilot_type_from_mav_autopilot() -> None:
    """Verify AutopilotType.from_mav_autopilot mappings."""
    assert AutopilotType.from_mav_autopilot(3) == AutopilotType.ARDUPILOT
    assert AutopilotType.from_mav_autopilot(0) == AutopilotType.GENERIC
    assert AutopilotType.from_mav_autopilot(999) == AutopilotType.UNKNOWN


def test_vehicle_identity_to_dict(sample_rover_identity: VehicleIdentity) -> None:
    """Verify sample_rover_identity.to_dict returns string enum values."""
    data = sample_rover_identity.to_dict()
    assert data["system_id"] == 2
    assert data["component_id"] == 1
    assert data["vehicle_type"] == "rover"
    assert data["autopilot_type"] == "generic"
    assert data["firmware_version"] == "1.0.0"


def test_dataclasses_are_frozen() -> None:
    """Verify core dataclasses cannot be mutated after creation."""
    att = AttitudeData(roll=0.1, pitch=0.2, yaw=0.3)
    with pytest.raises(FrozenInstanceError):
        att.roll = 0.5  # type: ignore[misc]

    param = Parameter(param_id="SPEED", value=1.0, param_type=9, param_index=1)
    with pytest.raises(FrozenInstanceError):
        param.value = 2.0  # type: ignore[misc]


def test_telemetry_snapshot_to_dict() -> None:
    """Verify TelemetrySnapshot.to_dict correctly converts nested objects."""
    att = AttitudeData(roll=0.0, pitch=0.0, yaw=1.57)
    gps = GpsData(lat=28.6, lon=77.2, alt=10.0, fix_type=3, satellites=10)
    batt = BatteryData(voltage=11.1, current=2.5, remaining=85)
    rc = [1500] * 18
    snap = TelemetrySnapshot(
        timestamp=100.0,
        attitude=att,
        gps=gps,
        battery=batt,
        rc_channels=rc,
    )
    result = snap.to_dict()
    assert result["timestamp"] == 100.0
    assert result["attitude"] == att.to_dict()
    assert result["gps"] == gps.to_dict()
    assert result["battery"] == batt.to_dict()
    assert result["rc_channels"] == rc
