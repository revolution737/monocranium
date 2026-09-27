from __future__ import annotations

import json
import logging
from typing import Any

import websockets

from src.core.auto_config import AutoConfigEngine
from src.core.connection import ConnectionManager
from src.core.parameter_store import ParameterStore
from src.core.telemetry_bus import TelemetryBus
from src.core.vehicle_registry import VehicleRegistry
from src.server.ws_handlers import dispatch_command

logger = logging.getLogger(__name__)

LISTENED_EVENTS: list[str] = [
    "telemetry.attitude",
    "telemetry.gps",
    "telemetry.position",
    "telemetry.hud",
    "telemetry.battery",
    "telemetry.rc",
    "vehicle.discovered",
    "vehicle.updated",
    "vehicle.lost",
    "vehicle.status",
    "param.updated",
    "param.bulk_loaded",
]


class WebSocketServer:
    """WebSocket server bridging browser clients and the Core Bridge."""

    def __init__(
        self,
        bus: TelemetryBus,
        registry: VehicleRegistry,
        param_store: ParameterStore,
        auto_config: AutoConfigEngine,
        conn_mgr: ConnectionManager,
        host: str = "0.0.0.0",
        port: int = 8765,
    ) -> None:
        """Initialise WebSocket server instance.

        Args:
            bus: TelemetryBus for listening to event streams.
            registry: VehicleRegistry instance.
            param_store: ParameterStore instance.
            auto_config: AutoConfigEngine instance.
            conn_mgr: ConnectionManager instance.
            host: Interface host address.
            port: Local TCP port for WebSocket connections.
        """
        self._bus = bus
        self._registry = registry
        self._param_store = param_store
        self._auto_config = auto_config
        self._conn_mgr = conn_mgr
        self._host = host
        self._port = port
        self._clients: set[Any] = set()
        self._server: Any | None = None

    @property
    def client_count(self) -> int:
        """Number of currently connected WebSocket browser clients."""
        return len(self._clients)

    async def _on_bus_event(self, event_type: str, data: dict[str, Any]) -> None:
        """Forward telemetry bus events to all connected WebSocket clients."""
        if event_type.startswith("telemetry."):
            logger.info(
                "Telemetry event before broadcast: %s %s (clients=%d)",
                event_type,
                data,
                len(self._clients),
            )
        if not self._clients:
            return
        payload = {"event": event_type, "data": data}
        await self.broadcast(payload)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Encode message to JSON and transmit to all active client connections.

        Args:
            message: Dictionary payload to broadcast.
        """
        if not self._clients:
            return
        raw = json.dumps(message)
        for client in list(self._clients):
            try:
                await client.send(raw)
                if str(message.get("event", "")).startswith("telemetry."):
                    logger.info("Telemetry WebSocket sent: %s", message)
            except (websockets.exceptions.ConnectionClosed, OSError) as e:
                logger.debug("Failed broadcasting to client: %s", e)
                self._clients.discard(client)

    async def _handler(self, websocket: Any) -> None:
        """Handle lifecycle and command exchange for a single client."""
        self._clients.add(websocket)
        remote = getattr(websocket, "remote_address", "client")
        logger.info("WebSocket client connected: %s", remote)
        try:
            async for raw_msg in websocket:
                response = await dispatch_command(
                    str(raw_msg),
                    self._registry,
                    self._param_store,
                    self._auto_config,
                    self._conn_mgr,
                )
                await websocket.send(json.dumps(response))
        except websockets.exceptions.ConnectionClosed as e:
            logger.debug("WebSocket client disconnected: %s", e)
        finally:
            self._clients.discard(websocket)

    async def start(self) -> None:
        """Start the WebSocket server and register telemetry event subscriptions."""
        for event_name in LISTENED_EVENTS:
            await self._bus.subscribe(event_name, self._on_bus_event)

        self._server = await websockets.serve(self._handler, self._host, self._port)
        logger.info("WebSocket server listening on %s:%d", self._host, self._port)

    async def stop(self) -> None:
        """Stop server, unsubscribe event listeners, and close client connections."""
        for event_name in LISTENED_EVENTS:
            try:
                await self._bus.unsubscribe(event_name, self._on_bus_event)
            except ValueError:
                pass

        if self._server is not None:
            self._server.close()
            await self._server.wait_closed()

        for client in list(self._clients):
            try:
                await client.close()
            except (websockets.exceptions.ConnectionClosed, OSError):
                pass
        self._clients.clear()
        logger.info("WebSocket server stopped")
