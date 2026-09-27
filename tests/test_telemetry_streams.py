"""Offline coverage of ArduPilot stream negotiation and connection lifecycle."""

import asyncio
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.core.telemetry_streams import TelemetryStreams
from src.core.types import AutopilotType, ConnectionState, VehicleIdentity, VehicleType


def _identity(autopilot: AutopilotType = AutopilotType.ARDUPILOT) -> VehicleIdentity:
    return VehicleIdentity(1, 1, VehicleType.COPTER, autopilot, "test")


def _ack(command: int = 511, result: int = 0, system: int = 1) -> SimpleNamespace:
    return SimpleNamespace(command=command, result=result,
                           get_srcSystem=lambda: system, get_srcComponent=lambda: 1)


@pytest.mark.asyncio
async def test_intervals_are_sequential_and_initialized_once() -> None:
    """Each accepted interval is sent once even when another heartbeat arrives."""
    streams, conn = TelemetryStreams(), MagicMock()
    sent = []

    async def send(msg: Any) -> None:
        sent.append(msg)
        streams.handle_ack(conn, _ack())

    conn.send_message = send
    task = streams.start(conn, _identity())
    assert task is not None
    assert streams.start(conn, _identity()) is task
    await task
    assert [(m.param1, m.param2) for m in sent] == [
        (30, 100000), (33, 200000), (24, 200000), (1, 500000), (74, 200000), (147, 500000),
    ]
    assert streams.start(conn, _identity()) is task


@pytest.mark.asyncio
@pytest.mark.parametrize("result", [3, None])
async def test_unsupported_or_timeout_falls_back(result: int | None) -> None:
    """An unsupported interval or absent ACK enables legacy groups once."""
    streams, conn = TelemetryStreams(ack_timeout_s=0.001), MagicMock()
    sent = []

    async def send(msg: Any) -> None:
        sent.append(msg)
        if result is not None and msg.get_type() == "COMMAND_LONG":
            streams.handle_ack(conn, _ack(result=result))

    conn.send_message = send
    task = streams.start(conn, _identity())
    assert task is not None
    await task
    assert len(sent) == 6
    assert [(m.req_stream_id, m.req_message_rate) for m in sent[1:]] == [
        (10, 10), (6, 5), (2, 5), (11, 5), (12, 2),
    ]


@pytest.mark.asyncio
@pytest.mark.parametrize("autopilot", [AutopilotType.GENERIC, AutopilotType.UNKNOWN])
async def test_non_ardupilot_is_untouched(autopilot: AutopilotType) -> None:
    """Generic simulators and PX4 identities do not trigger ArduPilot setup."""
    streams, conn = TelemetryStreams(), MagicMock()
    assert streams.start(conn, _identity(autopilot)) is None
    conn.send_message.assert_not_called()


@pytest.mark.asyncio
async def test_disconnect_cancels_and_allows_new_session() -> None:
    """Disconnect cancels pending ACK waits and permits setup on reconnection."""
    streams, conn = TelemetryStreams(), MagicMock()
    conn.send_message = AsyncMock()
    first = streams.start(conn, _identity())
    assert first is not None
    await asyncio.sleep(0)
    callback = conn.on_state_change.call_args.args[0]
    await callback(ConnectionState.DISCONNECTED)
    assert first.cancelled()
    second = streams.start(conn, _identity())
    assert second is not first
    await callback(ConnectionState.DISCONNECTED)


@pytest.mark.asyncio
async def test_unrelated_ack_does_not_advance_negotiation() -> None:
    """Other vehicles, components, and commands cannot acknowledge an interval."""
    streams, conn = TelemetryStreams(), MagicMock()
    conn.send_message = AsyncMock()
    task = streams.start(conn, _identity())
    assert task is not None
    await asyncio.sleep(0)
    streams.handle_ack(conn, _ack(command=400))
    streams.handle_ack(conn, _ack(system=2))
    streams.handle_ack(MagicMock(), _ack())
    await asyncio.sleep(0)
    assert conn.send_message.await_count == 1
    await conn.on_state_change.call_args.args[0](ConnectionState.DISCONNECTED)
    assert task.cancelled()
