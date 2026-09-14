from __future__ import annotations

import logging
from typing import TYPE_CHECKING

from src.core.types import VehicleIdentity

if TYPE_CHECKING:
    from src.core.telemetry_bus import TelemetryBus

logger = logging.getLogger(__name__)


class VehicleRegistry:
    """Registry maintaining active vehicle identities and lifecycle events."""

    def __init__(self, bus: TelemetryBus) -> None:
        """Initialise vehicle registry.

        Args:
            bus: TelemetryBus instance for publishing lifecycle events.
        """
        self._bus = bus
        self._vehicles: dict[int, VehicleIdentity] = {}

    async def register(self, identity: VehicleIdentity) -> None:
        """Register or update a vehicle identity.

        Publishes 'vehicle.updated' if the system_id is already tracked,
        otherwise publishes 'vehicle.discovered'.

        Args:
            identity: VehicleIdentity instance describing the vehicle.
        """
        is_update = identity.system_id in self._vehicles
        self._vehicles[identity.system_id] = identity
        event_name = "vehicle.updated" if is_update else "vehicle.discovered"
        await self._bus.publish(event_name, identity.to_dict())

    async def unregister(self, system_id: int) -> None:
        """Unregister a vehicle and publish a vehicle.lost event.

        Args:
            system_id: MAVLink system ID of the vehicle to remove.

        Raises:
            KeyError: If the vehicle is not currently registered.
        """
        if system_id not in self._vehicles:
            raise KeyError(f"Vehicle with system_id {system_id} is not registered")
        del self._vehicles[system_id]
        await self._bus.publish("vehicle.lost", {"system_id": system_id})

    def get(self, system_id: int) -> VehicleIdentity:
        """Retrieve the identity of a registered vehicle.

        Args:
            system_id: MAVLink system ID.

        Returns:
            VehicleIdentity instance.

        Raises:
            KeyError: If the vehicle is not found.
        """
        if system_id not in self._vehicles:
            raise KeyError(f"Vehicle with system_id {system_id} is not registered")
        return self._vehicles[system_id]

    def list_all(self) -> list[VehicleIdentity]:
        """Return a list of all currently registered vehicle identities.

        Returns:
            List of VehicleIdentity objects.
        """
        return list(self._vehicles.values())

    def is_registered(self, system_id: int) -> bool:
        """Check whether a vehicle with the given system ID is registered.

        Args:
            system_id: MAVLink system ID.

        Returns:
            True if registered, False otherwise.
        """
        return system_id in self._vehicles
