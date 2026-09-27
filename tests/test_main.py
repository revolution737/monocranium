from __future__ import annotations

import argparse
import asyncio
from unittest.mock import AsyncMock, call, patch

import pytest

from src.core.types import ConnectionEndpoint
from src.main import build_endpoints, parse_args, run_bridge


def _args(rover_port: int | None = 5770, no_rover: bool = False) -> argparse.Namespace:
    return argparse.Namespace(
        rover_host="127.0.0.1", rover_port=rover_port, rover_protocol="tcp",
        drone_host="127.0.0.1", drone_port=5771, drone_protocol="tcp",
        no_rover=no_rover, http_port=8080, ws_port=8765,
    )


@pytest.mark.parametrize("port, no_rover", [(5770, True), (0, False), (None, False)])
def test_disabled_rover_builds_only_drone_endpoint(port: int | None, no_rover: bool) -> None:
    """An explicit flag, zero port, or missing rover port omits rover discovery."""
    args = _args(port, no_rover)
    if port is None:
        delattr(args, "rover_port")

    assert build_endpoints(args) == [ConnectionEndpoint("127.0.0.1", 5771, "tcp")]


def test_rover_enabled_builds_both_endpoints() -> None:
    """The existing two-vehicle default remains available."""
    assert build_endpoints(_args()) == [
        ConnectionEndpoint("127.0.0.1", 5770, "tcp"),
        ConnectionEndpoint("127.0.0.1", 5771, "tcp"),
    ]


def test_zero_drone_port_is_rejected() -> None:
    """No configured vehicle may reach pymavlink through TCP port zero."""
    args = _args(rover_port=0)
    args.drone_port = 0
    with pytest.raises(ValueError, match="Drone MAVLink port"):
        build_endpoints(args)


def test_cli_accepts_rover_disable_flag(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bridge exposes a clear drone-only command-line option."""
    monkeypatch.setattr("sys.argv", ["monocranium", "--no-rover"])
    assert build_endpoints(parse_args()) == [ConnectionEndpoint("127.0.0.1", 5771, "tcp")]


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "port, no_rover, expected_ports",
    [(0, False, [5771]), (5770, True, [5771]), (5770, False, [5770, 5771])],
)
async def test_bridge_registers_only_enabled_endpoints(
    port: int, no_rover: bool, expected_ports: list[int],
) -> None:
    """Only enabled endpoints reach the connection manager and pymavlink."""
    stop_event = asyncio.Event()

    async def scan(engine: object, endpoints: list[ConnectionEndpoint]) -> list[object]:
        for endpoint in endpoints:
            await engine._conn_mgr.add_connection(endpoint)  # type: ignore[attr-defined]
        assert list(engine._conn_mgr._connections) == [  # type: ignore[attr-defined]
            ("127.0.0.1", expected_port) for expected_port in expected_ports
        ]
        stop_event.set()
        return []

    with (
        patch("src.main.HttpServer") as http_server,
        patch("src.main.WebSocketServer") as ws_server,
        patch("src.main.AutoConfigEngine.run_full_scan", scan),
        patch("src.core.protocol.mavutil.mavlink_connection") as mavlink,
    ):
        mavlink.return_value.recv_msg.return_value = None
        http_server.return_value.start = AsyncMock()
        http_server.return_value.stop = AsyncMock()
        ws_server.return_value.start = AsyncMock()
        ws_server.return_value.stop = AsyncMock()
        await run_bridge(_args(port, no_rover), stop_event)

    assert mavlink.call_args_list == [
        call(f"tcp:127.0.0.1:{expected_port}") for expected_port in expected_ports
    ]
    assert call("tcp:127.0.0.1:0") not in mavlink.call_args_list
