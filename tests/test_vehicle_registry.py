from __future__ import annotations

from typing import Any

import pytest

from src.core.telemetry_bus import TelemetryBus
from src.core.types import AutopilotType, VehicleIdentity, VehicleType
from src.core.vehicle_registry import VehicleRegistry


@pytest.mark.asyncio
async def test_register_new_vehicle(
    vehicle_registry: VehicleRegistry,
    sample_rover_identity: VehicleIdentity,
) -> None:
    """Verify register adds vehicle and get returns it."""
    await vehicle_registry.register(sample_rover_identity)

    assert vehicle_registry.is_registered(sample_rover_identity.system_id)
    retrieved = vehicle_registry.get(sample_rover_identity.system_id)
    assert retrieved == sample_rover_identity


@pytest.mark.asyncio
async def test_register_publishes_discovered_event(
    vehicle_registry: VehicleRegistry,
    telemetry_bus: TelemetryBus,
    sample_rover_identity: VehicleIdentity,
) -> None:
    """Verify first registration publishes vehicle.discovered."""
    discovered: list[dict[str, Any]] = []

    async def on_discovered(event: str, data: dict[str, Any]) -> None:
        discovered.append(data)

    await telemetry_bus.subscribe("vehicle.discovered", on_discovered)
    await vehicle_registry.register(sample_rover_identity)

    assert len(discovered) == 1
    assert discovered[0]["system_id"] == 2
    assert discovered[0]["vehicle_type"] == "rover"


@pytest.mark.asyncio
async def test_register_existing_publishes_updated_event(
    vehicle_registry: VehicleRegistry,
    telemetry_bus: TelemetryBus,
    sample_rover_identity: VehicleIdentity,
) -> None:
    """Verify re-registration of same vehicle publishes vehicle.updated."""
    updates: list[dict[str, Any]] = []

    async def on_updated(event: str, data: dict[str, Any]) -> None:
        updates.append(data)

    await telemetry_bus.subscribe("vehicle.updated", on_updated)

    # First register
    await vehicle_registry.register(sample_rover_identity)

    # Second register with modified version
    updated_identity = VehicleIdentity(
        system_id=sample_rover_identity.system_id,
        component_id=1,
        vehicle_type=VehicleType.ROVER,
        autopilot_type=AutopilotType.GENERIC,
        firmware_version="1.1.0",
    )
    await vehicle_registry.register(updated_identity)

    assert len(updates) == 1
    assert updates[0]["firmware_version"] == "1.1.0"


@pytest.mark.asyncio
async def test_unregister(
    vehicle_registry: VehicleRegistry,
    telemetry_bus: TelemetryBus,
    sample_rover_identity: VehicleIdentity,
) -> None:
    """Verify unregister removes vehicle and emits vehicle.lost event."""
    lost: list[dict[str, Any]] = []

    async def on_lost(event: str, data: dict[str, Any]) -> None:
        lost.append(data)

    await telemetry_bus.subscribe("vehicle.lost", on_lost)
    await vehicle_registry.register(sample_rover_identity)
    await vehicle_registry.unregister(sample_rover_identity.system_id)

    assert not vehicle_registry.is_registered(sample_rover_identity.system_id)
    assert len(lost) == 1
    assert lost[0]["system_id"] == 2


@pytest.mark.asyncio
async def test_unregister_nonexistent_raises(
    vehicle_registry: VehicleRegistry,
) -> None:
    """Verify unregistering an untracked vehicle raises KeyError."""
    with pytest.raises(KeyError, match="is not registered"):
        await vehicle_registry.unregister(999)


@pytest.mark.asyncio
async def test_list_all(
    vehicle_registry: VehicleRegistry,
    sample_rover_identity: VehicleIdentity,
) -> None:
    """Verify list_all returns all tracked vehicle identities."""
    v2 = VehicleIdentity(
        system_id=3,
        component_id=1,
        vehicle_type=VehicleType.UNKNOWN,
        autopilot_type=AutopilotType.GENERIC,
        firmware_version="0.9.0",
    )
    await vehicle_registry.register(sample_rover_identity)
    await vehicle_registry.register(v2)

    all_vehicles = vehicle_registry.list_all()
    assert len(all_vehicles) == 2
    system_ids = {v.system_id for v in all_vehicles}
    assert system_ids == {2, 3}
