from __future__ import annotations

from typing import Any

import pytest

from src.core.telemetry_bus import TelemetryBus


@pytest.mark.asyncio
async def test_subscribe_and_publish(telemetry_bus: TelemetryBus) -> None:
    """Verify subscribing a callback receives published events."""
    received: list[tuple[str, dict[str, Any]]] = []

    async def on_event(event_type: str, data: dict[str, Any]) -> None:
        received.append((event_type, data))

    await telemetry_bus.subscribe("telemetry.attitude", on_event)
    await telemetry_bus.publish("telemetry.attitude", {"roll": 0.1, "pitch": 0.2})

    assert len(received) == 1
    assert received[0] == ("telemetry.attitude", {"roll": 0.1, "pitch": 0.2})


@pytest.mark.asyncio
async def test_publish_no_subscribers(telemetry_bus: TelemetryBus) -> None:
    """Verify publishing to an event type with no subscribers does not raise."""
    await telemetry_bus.publish("nonexistent.event", {"key": "value"})


@pytest.mark.asyncio
async def test_unsubscribe(telemetry_bus: TelemetryBus) -> None:
    """Verify unsubscribed callbacks no longer receive published events."""
    calls: list[dict[str, Any]] = []

    async def on_event(event_type: str, data: dict[str, Any]) -> None:
        calls.append(data)

    await telemetry_bus.subscribe("test.event", on_event)
    await telemetry_bus.publish("test.event", {"msg": "hello"})
    assert len(calls) == 1

    await telemetry_bus.unsubscribe("test.event", on_event)
    await telemetry_bus.publish("test.event", {"msg": "world"})
    assert len(calls) == 1


@pytest.mark.asyncio
async def test_unsubscribe_nonexistent_raises(telemetry_bus: TelemetryBus) -> None:
    """Verify unsubscribing an unregistered callback raises ValueError."""
    async def dummy(event_type: str, data: dict[str, Any]) -> None:
        pass

    with pytest.raises(ValueError, match="is not subscribed"):
        await telemetry_bus.unsubscribe("unknown.event", dummy)


@pytest.mark.asyncio
async def test_subscriber_exception_does_not_block_others(telemetry_bus: TelemetryBus) -> None:
    """Verify an exception in one subscriber does not prevent others from running."""
    calls: list[str] = []

    async def failing_subscriber(event_type: str, data: dict[str, Any]) -> None:
        raise RuntimeError("Simulated failure")

    async def succeeding_subscriber(event_type: str, data: dict[str, Any]) -> None:
        calls.append("success")

    await telemetry_bus.subscribe("test.error", failing_subscriber)
    await telemetry_bus.subscribe("test.error", succeeding_subscriber)

    await telemetry_bus.publish("test.error", {"data": 123})
    assert calls == ["success"]
