from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from typing import Any, Callable, Coroutine

logger = logging.getLogger(__name__)


SubscriberCallback = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]


class TelemetryBus:
    """In-process publish/subscribe event bus for telemetry and system events.

    Event types follow the naming convention '<domain>.<action>'.
    Examples: 'telemetry.attitude', 'vehicle.discovered', 'param.updated'.
    """

    def __init__(self) -> None:
        """Initialise with empty subscriber registry and concurrency lock."""
        self._subscribers: dict[str, list[SubscriberCallback]] = defaultdict(list)
        self._lock: asyncio.Lock = asyncio.Lock()

    async def subscribe(
        self,
        event_type: str,
        callback: SubscriberCallback,
    ) -> None:
        """Register a callback for a specific event type.

        Args:
            event_type: The event type string (e.g., 'telemetry.attitude').
            callback: An async callable that accepts (event_type: str, data: dict).
        """
        async with self._lock:
            if callback not in self._subscribers[event_type]:
                self._subscribers[event_type].append(callback)

    async def unsubscribe(
        self,
        event_type: str,
        callback: SubscriberCallback,
    ) -> None:
        """Remove a callback from a specific event type.

        Args:
            event_type: The event type string.
            callback: The callback to remove.

        Raises:
            ValueError: If the callback is not registered for the event type.
        """
        async with self._lock:
            try:
                self._subscribers[event_type].remove(callback)
            except ValueError:
                raise ValueError(
                    f"Callback {callback} is not subscribed to '{event_type}'"
                )

    async def publish(self, event_type: str, data: dict[str, Any]) -> None:
        """Publish an event to all subscribers of that event type.

        Each subscriber is called with (event_type, data). If a subscriber
        raises an exception, it is logged and the remaining subscribers
        are still called.

        Args:
            event_type: The event type string.
            data: The event payload dictionary.
        """
        async with self._lock:
            callbacks = list(self._subscribers.get(event_type, []))

        for callback in callbacks:
            try:
                await callback(event_type, data)
            except Exception as e:
                logger.error(
                    "Subscriber %s raised exception for event '%s': %s",
                    callback,
                    event_type,
                    e,
                )
