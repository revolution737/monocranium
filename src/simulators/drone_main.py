from __future__ import annotations

import argparse
import asyncio
import logging

from src.simulators.drone_config import DEFAULT_DRONE_CONFIG
from src.simulators.drone_physics import DroneKinematics
from src.simulators.drone_sim import DroneMavlinkServer

logger = logging.getLogger(__name__)


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the drone simulator."""
    parser = argparse.ArgumentParser(description="Monocranium ArduPilot Copter SITL Simulator")
    parser.add_argument("--port", type=int, default=5771, help="MAVLink TCP port (default: 5771)")
    parser.add_argument("--system-id", type=int, default=3, help="MAVLink System ID (default: 3)")
    return parser.parse_args()


async def run_server(server: DroneMavlinkServer, stop_event: asyncio.Event) -> None:
    """Start and manage drone server lifecycle."""
    await server.start()
    try:
        await stop_event.wait()
    finally:
        await server.stop()


def main() -> None:
    """Application entry point for Drone SITL process."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    args = parse_args()
    logger.info("Initializing Monocranium Drone SITL Simulator on TCP port %d", args.port)

    config = DEFAULT_DRONE_CONFIG
    kinematics = DroneKinematics(config)
    server = DroneMavlinkServer(kinematics, config, port=args.port, system_id=args.system_id)

    stop_event = asyncio.Event()
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(run_server(server, stop_event))
    except KeyboardInterrupt:
        logger.info("Interrupted by user, shutting down drone simulator...")
        stop_event.set()


if __name__ == "__main__":
    main()
