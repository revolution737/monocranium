from __future__ import annotations

import argparse
import asyncio
import logging
import threading

import pygame

from src.simulators.rover_config import DEFAULT_ROVER_CONFIG
from src.simulators.rover_physics import RoverKinematics
from src.simulators.rover_renderer import RoverRenderer
from src.simulators.rover_sim import RoverMavlinkServer

logger = logging.getLogger(__name__)

TARGET_FPS: int = 60


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments for the rover simulator."""
    parser = argparse.ArgumentParser(description="Monocranium Virtual Rover Simulator")
    parser.add_argument("--port", type=int, default=5770, help="MAVLink TCP port (default: 5770)")
    parser.add_argument("--system-id", type=int, default=2, help="MAVLink System ID (default: 2)")
    parser.add_argument("--width", type=int, default=800, help="Window width (default: 800)")
    parser.add_argument("--height", type=int, default=600, help="Window height (default: 600)")
    return parser.parse_args()


def start_background_server(
    server: RoverMavlinkServer,
    loop: asyncio.AbstractEventLoop,
) -> threading.Thread:
    """Start the MAVLink TCP server inside a background daemon thread.

    Args:
        server: RoverMavlinkServer instance.
        loop: Dedicated asyncio event loop.

    Returns:
        Started background threading.Thread.
    """
    def run_async_loop() -> None:
        asyncio.set_event_loop(loop)
        loop.run_until_complete(server.start())
        loop.run_forever()

    thread = threading.Thread(target=run_async_loop, daemon=True, name="MavlinkServerThread")
    thread.start()
    return thread


def main() -> None:
    """Main simulation loop combining pygame UI and MAVLink TCP networking."""
    args = parse_args()
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    )
    logger.info("Initializing Monocranium Virtual Rover Simulator on TCP port %d", args.port)

    config = DEFAULT_ROVER_CONFIG
    center_x = float(args.width) / 2.0
    center_y = float(args.height) / 2.0
    kinematics = RoverKinematics(config, start_x=center_x, start_y=center_y)
    server = RoverMavlinkServer(kinematics, config, port=args.port, system_id=args.system_id)
    renderer = RoverRenderer(width=args.width, height=args.height)

    loop = asyncio.new_event_loop()
    start_background_server(server, loop)
    clock = pygame.time.Clock()

    running = True
    try:
        while running:
            dt = clock.tick(TARGET_FPS) / 1000.0
            running, keyboard_pwm = renderer.handle_events()

            throttle, steering = server.current_rc
            if throttle == config.pwm_center and steering == config.pwm_center:
                throttle = keyboard_pwm.get("throttle_pwm", config.pwm_center)
                steering = keyboard_pwm.get("steering_pwm", config.pwm_center)

            kinematics.update(throttle, steering, dt)
            conn_info = {"clients": server.client_count, "port": args.port}
            telem_info = {"speed": kinematics.speed_mps, "heading": kinematics.heading_deg}
            renderer.render_frame(kinematics, telem_info, conn_info)
    finally:
        logger.info("Shutting down rover simulator...")
        future = asyncio.run_coroutine_threadsafe(server.stop(), loop)
        try:
            future.result(timeout=2.0)
        except Exception as err:
            logger.debug("Server stop wait timed out: %s", err)
        loop.call_soon_threadsafe(loop.stop)
        renderer.cleanup()



if __name__ == "__main__":
    main()
