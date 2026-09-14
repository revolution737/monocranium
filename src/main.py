from __future__ import annotations

import argparse
import asyncio
import logging
from pathlib import Path

from src.core.auto_config import AutoConfigEngine
from src.core.connection import ConnectionManager
from src.core.parameter_store import ParameterStore
from src.core.telemetry_bus import TelemetryBus
from src.core.types import ConnectionEndpoint
from src.core.vehicle_registry import VehicleRegistry
from src.server.http_server import HttpServer
from src.server.ws_server import WebSocketServer

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Monocranium Core Bridge."""
    parser = argparse.ArgumentParser(description="Monocranium Core Bridge")
    parser.add_argument("--rover-host", type=str, default="127.0.0.1", help="Rover TCP host")
    parser.add_argument("--rover-port", type=int, default=5770, help="Rover TCP port")
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket server port")
    parser.add_argument("--http-port", type=int, default=8080, help="HTTP dashboard port")
    return parser.parse_args()


async def run_bridge(args: argparse.Namespace, stop_event: asyncio.Event) -> None:
    """Instantiate, wire, and run all Core Bridge subsystems.

    Args:
        args: Parsed command-line arguments.
        stop_event: Event signaling when to shut down.
    """
    bus = TelemetryBus()
    param_store = ParameterStore(bus)
    registry = VehicleRegistry(bus)
    conn_mgr = ConnectionManager()
    auto_config = AutoConfigEngine(conn_mgr, registry, param_store, bus)

    dist_dir = Path(__file__).resolve().parent.parent / "dashboard" / "dist"
    http_server = HttpServer(static_dir=dist_dir, host="0.0.0.0", port=args.http_port)
    ws_server = WebSocketServer(
        bus,
        registry,
        param_store,
        auto_config,
        conn_mgr,
        host="0.0.0.0",
        port=args.ws_port,
    )

    await http_server.start()
    await ws_server.start()

    endpoints = [ConnectionEndpoint(args.rover_host, args.rover_port, "tcp")]
    logger.info("Core Bridge running: WS port %d, HTTP port %d", args.ws_port, args.http_port)
    asyncio.create_task(auto_config.run_full_scan(endpoints))

    try:
        await stop_event.wait()
    finally:
        logger.info("Initiating graceful Core Bridge shutdown...")
        await ws_server.stop()
        await http_server.stop()
        await conn_mgr.close_all()


def main() -> None:
    """Application entry point for Core Bridge process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    args = parse_args()
    stop_event = asyncio.Event()

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_bridge(args, stop_event))
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down...")
        stop_event.set()


if __name__ == "__main__":
    main()
