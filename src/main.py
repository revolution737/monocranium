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
MIN_MAVLINK_PORT = 1
MAX_MAVLINK_PORT = 65535


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the Monocranium Core Bridge."""
    parser = argparse.ArgumentParser(description="Monocranium Core Bridge")
    parser.add_argument("--rover-host", type=str, default="127.0.0.1", help="Rover MAVLink host")
    parser.add_argument("--rover-port", type=int, default=5770, help="Rover MAVLink port")
    parser.add_argument(
        "--no-rover", action="store_true", help="Disable rover MAVLink discovery",
    )
    parser.add_argument(
        "--rover-protocol",
        type=str,
        choices=["tcp", "udp"],
        default="tcp",
        help="Rover MAVLink protocol",
    )
    parser.add_argument("--drone-host", type=str, default="127.0.0.1", help="Drone MAVLink host")
    parser.add_argument("--drone-port", type=int, default=5771, help="Drone MAVLink port")
    parser.add_argument(
        "--drone-protocol",
        type=str,
        choices=["tcp", "udp"],
        default="tcp",
        help="Drone MAVLink protocol",
    )
    parser.add_argument("--ws-port", type=int, default=8765, help="WebSocket server port")
    parser.add_argument("--http-port", type=int, default=8080, help="HTTP dashboard port")
    return parser.parse_args()


def build_endpoints(args: argparse.Namespace) -> list[ConnectionEndpoint]:
    """Select configured MAVLink endpoints before starting any connections."""
    if not MIN_MAVLINK_PORT <= args.drone_port <= MAX_MAVLINK_PORT:
        raise ValueError("Drone MAVLink port must be between 1 and 65535")
    endpoints: list[ConnectionEndpoint] = []
    rover_port = getattr(args, "rover_port", None)
    if not getattr(args, "no_rover", False) and rover_port not in (None, 0):
        if not MIN_MAVLINK_PORT <= rover_port <= MAX_MAVLINK_PORT:
            raise ValueError("Rover MAVLink port must be between 1 and 65535")
        endpoints.append(ConnectionEndpoint(
            args.rover_host, rover_port, args.rover_protocol,
        ))
    endpoints.append(ConnectionEndpoint(args.drone_host, args.drone_port, args.drone_protocol))
    return endpoints


async def run_bridge(args: argparse.Namespace, stop_event: asyncio.Event) -> None:
    """Instantiate, wire, and run all Core Bridge subsystems.

    Args:
        args: Parsed command-line arguments.
        stop_event: Event signaling when to shut down.
    """
    endpoints = build_endpoints(args)
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
