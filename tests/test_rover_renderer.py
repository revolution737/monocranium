"""Render clock behavior without initializing a display."""

from unittest.mock import MagicMock

import pytest

from src.simulators.rover_renderer import RoverRenderer


def test_tick_returns_elapsed_seconds() -> None:
    """The renderer owns pygame timing and reports SI seconds."""
    renderer = object.__new__(RoverRenderer)
    renderer._clock = MagicMock()
    renderer._clock.tick.return_value = 20
    assert renderer.tick(60) == pytest.approx(0.02)
    renderer._clock.tick.assert_called_once_with(60)


def test_tick_rejects_non_positive_frame_rate() -> None:
    """An invalid target FPS must fail before using the pygame clock."""
    renderer = object.__new__(RoverRenderer)
    renderer._clock = MagicMock()
    with pytest.raises(ValueError):
        renderer.tick(0)
    renderer._clock.tick.assert_not_called()
