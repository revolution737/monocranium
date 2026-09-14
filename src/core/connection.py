from __future__ import annotations

import asyncio
import logging
import time
from typing import Any, Callable, Coroutine

from src.core.protocol import create_mav_connection
from src.core.types import ConnectionEndpoint, ConnectionState

logger = logging.getLogger(__name__)

HEARTBEAT_TIMEOUT_S: float = 5.0
HEARTBEAT_DISCONNECT_S: float = 15.0
CONNECT_TIMEOUT_S: float = 10.0
READ_LOOP_SLEEP_S: float = 0.01

MessageHandler = Callable[[Any], Coroutine[Any, Any, None]]
StateHandler = Callable[[ConnectionState], Coroutine[Any, Any, None]]


class MavlinkConnection:
    """Manages an individual MAVLink connection and its heartbeat health."""

    def __init__(self, endpoint: ConnectionEndpoint) -> None:
        """Initialise connection wrapper for the specified endpoint.

        Args:
            endpoint: Remote or local endpoint configuration.
        """
        self._endpoint = endpoint
        self._state = ConnectionState.DISCONNECTED
        self._last_heartbeat_time: float = 0.0
        self._mav_conn: Any | None = None
        self._read_task: asyncio.Task[None] | None = None
        self._monitor_task: asyncio.Task[None] | None = None
        self._message_handlers: list[MessageHandler] = []
        self._state_handlers: list[StateHandler] = []

    @property
    def endpoint(self) -> ConnectionEndpoint:
        """Connection endpoint descriptor."""
        return self._endpoint

    @property
    def state(self) -> ConnectionState:
        """Current lifecycle connection state."""
        return self._state

    @property
    def last_heartbeat_time(self) -> float:
        """Timestamp of the most recently received heartbeat."""
        return self._last_heartbeat_time

    def on_message(self, handler: MessageHandler) -> None:
        """Register a callback for incoming parsed MAVLink messages."""
        self._message_handlers.append(handler)

    def on_state_change(self, handler: StateHandler) -> None:
        """Register a callback for connection state transitions."""
        self._state_handlers.append(handler)

    async def _set_state(self, new_state: ConnectionState) -> None:
        """Set connection state and notify registered listeners."""
        if self._state == new_state:
            return
        logger.info(
            "Connection %s state transition: %s -> %s",
            self._endpoint.address,
            self._state.value,
            new_state.value,
        )
        self._state = new_state
        for handler in self._state_handlers:
            try:
                await handler(new_state)
            except Exception as e:
                logger.error("State change handler error: %s", e)

    async def connect(self) -> bool:
        """Establish MAVLink connection and start read and monitor loops.

        Returns:
            True if connection initialized successfully.
        """
        await self._set_state(ConnectionState.CONNECTING)
        try:
            self._mav_conn = create_mav_connection(self._endpoint)
            self._read_task = asyncio.create_task(self._read_loop())
            self._monitor_task = asyncio.create_task(self._health_monitor_loop())
            return True
        except (ConnectionError, OSError, ValueError) as e:
            logger.error(
                "Failed to connect to %s:%d: %s",
                self._endpoint.address,
                self._endpoint.port,
                e,
            )
            await self._set_state(ConnectionState.DISCONNECTED)
            return False

    async def disconnect(self) -> None:
        """Disconnect, cancel tasks, and close socket."""
        if self._read_task:
            self._read_task.cancel()
        if self._monitor_task:
            self._monitor_task.cancel()
        if self._mav_conn and hasattr(self._mav_conn, "close"):
            try:
                self._mav_conn.close()
            except (OSError, AttributeError) as e:
                logger.debug("Error closing connection: %s", e)
        self._mav_conn = None
        await self._set_state(ConnectionState.DISCONNECTED)

    async def send_message(self, msg: Any) -> None:
        """Send a MAVLink message over the connection.

        Args:
            msg: MAVLink message to transmit.
        """
        if self._mav_conn and hasattr(self._mav_conn, "mav"):
            self._mav_conn.mav.send(msg)

    async def _read_loop(self) -> None:
        """Asynchronously poll for incoming messages."""
        while True:
            try:
                if self._mav_conn is not None:
                    msg = self._mav_conn.recv_msg()
                    if msg is not None:
                        await self._process_received_msg(msg)
                await asyncio.sleep(READ_LOOP_SLEEP_S)
            except asyncio.CancelledError:
                break
            except (ConnectionError, OSError) as e:
                logger.warning("Read error on %s: %s", self._endpoint.address, e)
                await self._set_state(ConnectionState.DISCONNECTED)
                break

    async def _process_received_msg(self, msg: Any) -> None:
        """Handle incoming message and update heartbeat tracker."""
        msg_type = getattr(msg, "get_type", lambda: "")()
        if msg_type == "HEARTBEAT":
            self._last_heartbeat_time = time.time()
            if self._state != ConnectionState.CONNECTED:
                await self._set_state(ConnectionState.CONNECTED)

        for handler in self._message_handlers:
            try:
                await handler(msg)
            except Exception as e:
                logger.error("Message handler error for %s: %s", msg_type, e)

    async def _health_monitor_loop(self) -> None:
        """Monitor elapsed time since last heartbeat."""
        while True:
            try:
                await asyncio.sleep(1.0)
                if self._state == ConnectionState.CONNECTED:
                    if time.time() - self._last_heartbeat_time > HEARTBEAT_TIMEOUT_S:
                        await self._set_state(ConnectionState.HEARTBEAT_LOST)
                elif self._state == ConnectionState.HEARTBEAT_LOST:
                    if time.time() - self._last_heartbeat_time > HEARTBEAT_DISCONNECT_S:
                        await self._set_state(ConnectionState.DISCONNECTED)
            except asyncio.CancelledError:
                break


class ConnectionManager:
    """Manages pool of active MAVLink connections."""

    def __init__(self) -> None:
        """Initialise connection manager with empty pool."""
        self._connections: dict[tuple[str, int], MavlinkConnection] = {}

    async def add_connection(self, endpoint: ConnectionEndpoint) -> MavlinkConnection:
        """Add and connect a new endpoint.

        Args:
            endpoint: ConnectionEndpoint to instantiate.

        Returns:
            The established MavlinkConnection.
        """
        key = (endpoint.address, endpoint.port)
        if key in self._connections:
            return self._connections[key]

        conn = MavlinkConnection(endpoint)
        self._connections[key] = conn
        await conn.connect()
        return conn

    async def remove_connection(self, endpoint: ConnectionEndpoint) -> None:
        """Disconnect and remove an endpoint from the manager.

        Args:
            endpoint: Target endpoint to remove.
        """
        key = (endpoint.address, endpoint.port)
        conn = self._connections.pop(key, None)
        if conn:
            await conn.disconnect()

    def get_connection(self, endpoint: ConnectionEndpoint) -> MavlinkConnection | None:
        """Retrieve connection instance for an endpoint if present.

        Args:
            endpoint: Endpoint to look up.

        Returns:
            MavlinkConnection or None.
        """
        return self._connections.get((endpoint.address, endpoint.port))

    def list_connections(self) -> list[MavlinkConnection]:
        """Return list of all managed connections.

        Returns:
            List of MavlinkConnection objects.
        """
        return list(self._connections.values())

    async def close_all(self) -> None:
        """Disconnect and clear all managed connections."""
        for conn in list(self._connections.values()):
            await conn.disconnect()
        self._connections.clear()
