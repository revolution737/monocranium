from __future__ import annotations

import pytest

from src.core.parameter_store import ParameterStore
from src.core.telemetry_bus import TelemetryBus
from src.core.types import (
    AutopilotType,
    Parameter,
    VehicleIdentity,
    VehicleType,
)
from src.core.vehicle_registry import VehicleRegistry


@pytest.fixture
def telemetry_bus() -> TelemetryBus:
    """Provide a fresh TelemetryBus instance."""
    return TelemetryBus()


@pytest.fixture
def param_store(telemetry_bus: TelemetryBus) -> ParameterStore:
    """Provide a fresh ParameterStore instance."""
    return ParameterStore(telemetry_bus)


@pytest.fixture
def vehicle_registry(telemetry_bus: TelemetryBus) -> VehicleRegistry:
    """Provide a fresh VehicleRegistry instance."""
    return VehicleRegistry(telemetry_bus)


@pytest.fixture
def sample_rover_identity() -> VehicleIdentity:
    """A VehicleIdentity representing a rover with system_id=2."""
    return VehicleIdentity(
        system_id=2,
        component_id=1,
        vehicle_type=VehicleType.ROVER,
        autopilot_type=AutopilotType.GENERIC,
        firmware_version="1.0.0",
    )


@pytest.fixture
def sample_parameters() -> list[Parameter]:
    """A list of 5 test parameters."""
    return [
        Parameter(param_id="SYSID_THISMAV", value=2.0, param_type=6, param_index=0),
        Parameter(param_id="WHEEL_DIA_MM", value=130.0, param_type=9, param_index=1),
        Parameter(param_id="WHEEL_BASE_MM", value=250.0, param_type=9, param_index=2),
        Parameter(param_id="MOT_MAX_RPM", value=6000.0, param_type=9, param_index=3),
        Parameter(param_id="BATT_VOLT", value=11.1, param_type=9, param_index=4),
    ]
