"""Once-per-connection ArduPilot telemetry negotiation without blocking reception."""

from __future__ import annotations

import asyncio
import logging
from typing import Any

from src.core.connection import MavlinkConnection
from src.core.protocol import (
    MAV_CMD_SET_MESSAGE_INTERVAL,
    create_data_stream_msg,
    create_message_interval_msg,
)
from src.core.types import AutopilotType, ConnectionState, VehicleIdentity

logger = logging.getLogger(__name__)
ACK_TIMEOUT_S = 2.0
MAV_RESULT_ACCEPTED = 0
MAV_RESULT_IN_PROGRESS = 5
MESSAGE_RATES = (
    ("ATTITUDE", 30, 10),
    ("GLOBAL_POSITION_INT", 33, 5),
    ("GPS_RAW_INT", 24, 5),
    ("SYS_STATUS", 1, 2),
    ("VFR_HUD", 74, 5),
    ("BATTERY_STATUS", 147, 2),
)
# Legacy groups cannot independently set rates for every message in a group.
LEGACY_RATES = ((10, 10), (6, 5), (2, 5), (11, 5), (12, 2))
StreamKey = tuple[MavlinkConnection, int, int]


class TelemetryStreams:
    """Serialize interval requests and retain completion until the connection ends."""

    def __init__(self, ack_timeout_s: float = ACK_TIMEOUT_S) -> None:
        """Initialize negotiation state with a bounded ACK timeout."""
        self._ack_timeout_s = ack_timeout_s
        self._tasks: dict[StreamKey, asyncio.Task[None]] = {}
        self._pending: dict[StreamKey, asyncio.Future[int]] = {}
        self._watched: set[MavlinkConnection] = set()

    def start(
        self, conn: MavlinkConnection, identity: VehicleIdentity,
    ) -> asyncio.Task[None] | None:
        """Start once for an ArduPilot identity on this connection; skip other autopilots."""
        if identity.autopilot_type != AutopilotType.ARDUPILOT:
            return None
        key = (conn, identity.system_id, identity.component_id)
        if key not in self._tasks:
            if conn not in self._watched:
                async def state_changed(state: ConnectionState) -> None:
                    await self._reset_connection(conn, state)
                conn.on_state_change(state_changed)
                self._watched.add(conn)
            logger.info("Vehicle heartbeat detected: system %d", identity.system_id)
            self._tasks[key] = asyncio.create_task(self._initialize(key))
        return self._tasks[key]

    def handle_ack(self, conn: MavlinkConnection, msg: Any) -> None:
        """Route only interval ACKs from the exact source on the requesting connection."""
        if msg.command != MAV_CMD_SET_MESSAGE_INTERVAL or msg.result == MAV_RESULT_IN_PROGRESS:
            return
        key = (conn, msg.get_srcSystem(), msg.get_srcComponent())
        pending = self._pending.get(key)
        if pending is not None and not pending.done():
            pending.set_result(int(msg.result))

    async def _reset_connection(self, conn: MavlinkConnection, state: ConnectionState) -> None:
        if state not in (ConnectionState.DISCONNECTED, ConnectionState.CONNECTING):
            return
        tasks = [self._tasks.pop(key) for key in list(self._tasks) if key[0] is conn]
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)

    async def _initialize(self, key: StreamKey) -> None:
        logger.info("Requesting telemetry streams for system %d...", key[1])
        try:
            for name, message_id, rate in MESSAGE_RATES:
                if not await self._request_interval(key, message_id, rate):
                    await self._legacy_fallback(key)
                    return
                logger.info("Requested %s @%dHz (acknowledged)", name, rate)
            logger.info("Telemetry stream initialization complete for system %d", key[1])
        except (OSError, ConnectionError, ValueError) as exc:
            logger.error("Telemetry stream initialization failed for system %d: %s", key[1], exc)

    async def _request_interval(self, key: StreamKey, message_id: int, rate: int) -> bool:
        conn, system_id, component_id = key
        future: asyncio.Future[int] = asyncio.get_running_loop().create_future()
        self._pending[key] = future
        try:
            await conn.send_message(create_message_interval_msg(
                system_id, component_id, message_id, rate,
            ))
            result = await asyncio.wait_for(future, self._ack_timeout_s)
            if result != MAV_RESULT_ACCEPTED:
                logger.warning(
                    "SET_MESSAGE_INTERVAL rejected: result=%d, system=%d", result, system_id,
                )
            return result == MAV_RESULT_ACCEPTED
        except asyncio.TimeoutError:
            logger.warning("SET_MESSAGE_INTERVAL ACK timed out for system %d", system_id)
            return False
        finally:
            self._pending.pop(key, None)

    async def _legacy_fallback(self, key: StreamKey) -> None:
        conn, system_id, component_id = key
        logger.warning("Falling back to REQUEST_DATA_STREAM for system %d", system_id)
        for stream_id, rate in LEGACY_RATES:
            await conn.send_message(
                create_data_stream_msg(system_id, component_id, stream_id, rate),
            )
            logger.info("Requested legacy stream %d @%dHz", stream_id, rate)
        logger.info(
            "Telemetry stream initialization complete for system %d (legacy requests sent; "
            "delivery must be verified from incoming telemetry)", system_id,
        )
