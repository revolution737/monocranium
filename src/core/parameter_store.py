from __future__ import annotations

import json
import logging
from typing import TYPE_CHECKING

from src.core.types import Parameter

if TYPE_CHECKING:
    from src.core.telemetry_bus import TelemetryBus

logger = logging.getLogger(__name__)


class ParameterStore:
    """In-memory cache of MAVLink parameters, keyed by system_id and param_id."""

    def __init__(self, bus: TelemetryBus) -> None:
        """Initialise empty parameter store.

        Args:
            bus: TelemetryBus instance for publishing parameter change events.
        """
        self._bus = bus
        self._store: dict[int, dict[str, Parameter]] = {}

    async def upsert(self, system_id: int, param: Parameter) -> None:
        """Insert or update a parameter for a vehicle.

        Args:
            system_id: MAVLink system ID of the vehicle.
            param: Parameter instance to insert or update.
        """
        if system_id not in self._store:
            self._store[system_id] = {}
        self._store[system_id][param.param_id] = param
        await self._bus.publish(
            "param.updated",
            {"system_id": system_id, "param": param.to_dict()},
        )

    async def bulk_load(self, system_id: int, params: list[Parameter]) -> None:
        """Replace all parameters for a vehicle with a new list.

        Args:
            system_id: MAVLink system ID of the vehicle.
            params: Complete list of parameters.
        """
        self._store[system_id] = {p.param_id: p for p in params}
        await self._bus.publish(
            "param.bulk_loaded",
            {"system_id": system_id, "count": len(params)},
        )

    def get(self, system_id: int, param_id: str) -> Parameter:
        """Retrieve a specific parameter for a vehicle.

        Args:
            system_id: MAVLink system ID.
            param_id: Parameter name/id.

        Returns:
            The requested Parameter instance.

        Raises:
            KeyError: If the system_id or param_id does not exist.
        """
        if system_id not in self._store or param_id not in self._store[system_id]:
            raise KeyError(f"Parameter '{param_id}' not found for system {system_id}")
        return self._store[system_id][param_id]

    def get_all(self, system_id: int) -> list[Parameter]:
        """Return all parameters for a system, sorted by parameter index.

        Args:
            system_id: MAVLink system ID.

        Returns:
            List of Parameter instances sorted by param_index, or empty list.
        """
        if system_id not in self._store:
            return []
        return sorted(self._store[system_id].values(), key=lambda p: p.param_index)

    def get_count(self, system_id: int) -> int:
        """Return the count of parameters for a system.

        Args:
            system_id: MAVLink system ID.

        Returns:
            Number of stored parameters.
        """
        return len(self._store.get(system_id, {}))

    def clear(self, system_id: int) -> None:
        """Remove all parameters for a system.

        Args:
            system_id: MAVLink system ID.
        """
        self._store.pop(system_id, None)

    def export_json(self, system_id: int) -> str:
        """Export all parameters for a system as a formatted JSON string.

        Args:
            system_id: MAVLink system ID.

        Returns:
            Indented JSON string representing the parameter dicts.
        """
        params = [p.to_dict() for p in self.get_all(system_id)]
        return json.dumps(params, indent=2)
