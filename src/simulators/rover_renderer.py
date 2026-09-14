from __future__ import annotations

import logging
import math
from typing import Any

import pygame

from src.simulators.rover_physics import PIXELS_PER_METER, RoverKinematics

logger = logging.getLogger(__name__)

COLOR_BACKGROUND = (26, 26, 46)
COLOR_GRID = (22, 33, 62)
COLOR_ROVER_BODY = (233, 69, 96)
COLOR_ROVER_WHEELS = (83, 52, 131)
COLOR_HEADING_ARROW = (255, 211, 105)
COLOR_HUD_TEXT = (230, 237, 243)
COLOR_HUD_ACCENT = (88, 166, 255)

ROVER_WIDTH_PX: int = 50
ROVER_HEIGHT_PX: int = 32
WHEEL_WIDTH_PX: int = 14
WHEEL_HEIGHT_PX: int = 7
GRID_STEP_PX: int = PIXELS_PER_METER
KEY_PWM_HIGH: int = 1700
KEY_PWM_LOW: int = 1300
KEY_PWM_CENTER: int = 1500


class RoverRenderer:
    """Pygame visual renderer for the 4WD skid-steer virtual rover."""

    def __init__(
        self,
        width: int = 800,
        height: int = 600,
        title: str = "Monocranium Rover Simulator",
    ) -> None:
        """Initialise pygame display window and graphics context.

        Args:
            width: Window width in pixels.
            height: Window height in pixels.
            title: Window title text.
        """
        pygame.init()
        pygame.display.set_caption(title)
        self._width = width
        self._height = height
        self._screen = pygame.display.set_mode((width, height))
        self._clock = pygame.time.Clock()
        self._font = pygame.font.SysFont("monospace", 13)
        self._title_font = pygame.font.SysFont("monospace", 15, bold=True)

    def _draw_grid(self) -> None:
        """Draw 1-meter coordinate grid lines."""
        for x in range(0, self._width, GRID_STEP_PX):
            pygame.draw.line(self._screen, COLOR_GRID, (x, 0), (x, self._height))
        for y in range(0, self._height, GRID_STEP_PX):
            pygame.draw.line(self._screen, COLOR_GRID, (0, y), (self._width, y))

    def _draw_rover(self, rover: RoverKinematics) -> None:
        """Draw rotated chassis, wheels, and heading arrow."""
        x, y = rover.position
        heading_deg = rover.heading_deg

        # Rover chassis surface
        chassis_surf = pygame.Surface((ROVER_WIDTH_PX, ROVER_HEIGHT_PX), pygame.SRCALPHA)

        # Wheels at 4 corners
        wheel_surf = pygame.Surface((WHEEL_WIDTH_PX, WHEEL_HEIGHT_PX))
        wheel_surf.fill(COLOR_ROVER_WHEELS)
        chassis_surf.blit(wheel_surf, (2, 0))
        chassis_surf.blit(wheel_surf, (ROVER_WIDTH_PX - WHEEL_WIDTH_PX - 2, 0))
        chassis_surf.blit(wheel_surf, (2, ROVER_HEIGHT_PX - WHEEL_HEIGHT_PX))
        bottom_right_pos = (ROVER_WIDTH_PX - WHEEL_WIDTH_PX - 2, ROVER_HEIGHT_PX - WHEEL_HEIGHT_PX)
        chassis_surf.blit(wheel_surf, bottom_right_pos)

        # Main chassis body
        body_rect = pygame.Rect(6, 4, ROVER_WIDTH_PX - 12, ROVER_HEIGHT_PX - 8)
        pygame.draw.rect(chassis_surf, COLOR_ROVER_BODY, body_rect, border_radius=4)

        # Rotate chassis surface
        rotated_surf = pygame.transform.rotate(chassis_surf, -heading_deg)
        new_rect = rotated_surf.get_rect(center=(int(x), int(y)))
        self._screen.blit(rotated_surf, new_rect.topleft)

        # Heading direction indicator line
        rad = rover.heading_rad
        end_x = int(x + math.cos(rad) * 35)
        end_y = int(y + math.sin(rad) * 35)
        pygame.draw.line(self._screen, COLOR_HEADING_ARROW, (int(x), int(y)), (end_x, end_y), 2)

    def _draw_hud(
        self,
        rover: RoverKinematics,
        telemetry: dict[str, Any],
        connection: dict[str, Any],
    ) -> None:
        """Draw HUD status and diagnostic text."""
        x, y = rover.position
        fps = int(self._clock.get_fps())
        lines = [
            f"SPEED: {rover.speed_mps:.2f} m/s",
            f"HEADING: {rover.heading_deg:.1f}°",
            f"POS: ({x:.1f}, {y:.1f}) px",
            f"MAV CLIENTS: {connection.get('clients', 0)} (Port {connection.get('port', 5770)})",
            f"FPS: {fps}",
        ]
        title = self._title_font.render("MONOCRANIUM ROVER SIMULATOR", True, COLOR_HUD_ACCENT)
        self._screen.blit(title, (16, 14))

        for idx, line in enumerate(lines):
            txt = self._font.render(line, True, COLOR_HUD_TEXT)
            self._screen.blit(txt, (16, 38 + (idx * 18)))

        hint = self._font.render("DRIVE: WASD / Arrow Keys | ESC: Exit", True, COLOR_HUD_ACCENT)
        self._screen.blit(hint, (16, self._height - 26))

    def render_frame(
        self,
        rover: RoverKinematics,
        telemetry_dict: dict[str, Any],
        connection_info: dict[str, Any],
    ) -> None:
        """Render a complete animation frame and flip display buffers.

        Args:
            rover: RoverKinematics instance.
            telemetry_dict: Dictionary containing telemetry values.
            connection_info: Dictionary containing connection status info.
        """
        self._screen.fill(COLOR_BACKGROUND)
        self._draw_grid()
        self._draw_rover(rover)
        self._draw_hud(rover, telemetry_dict, connection_info)
        pygame.display.flip()

    def handle_events(self) -> tuple[bool, dict[str, int]]:
        """Process pygame events and translate active keyboard inputs to PWM.

        Returns:
            Tuple of (should_continue, {"throttle_pwm": int, "steering_pwm": int}).
        """
        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                return (False, {"throttle_pwm": KEY_PWM_CENTER, "steering_pwm": KEY_PWM_CENTER})
            if event.type == pygame.KEYDOWN and event.key == pygame.K_ESCAPE:
                return (False, {"throttle_pwm": KEY_PWM_CENTER, "steering_pwm": KEY_PWM_CENTER})

        keys = pygame.key.get_pressed()
        throttle = KEY_PWM_CENTER
        steering = KEY_PWM_CENTER

        if keys[pygame.K_UP] or keys[pygame.K_w]:
            throttle = KEY_PWM_HIGH
        elif keys[pygame.K_DOWN] or keys[pygame.K_s]:
            throttle = KEY_PWM_LOW

        if keys[pygame.K_RIGHT] or keys[pygame.K_d]:
            steering = KEY_PWM_HIGH
        elif keys[pygame.K_LEFT] or keys[pygame.K_a]:
            steering = KEY_PWM_LOW

        return (True, {"throttle_pwm": throttle, "steering_pwm": steering})

    def cleanup(self) -> None:
        """Shut down pygame graphics and release window."""
        pygame.quit()
