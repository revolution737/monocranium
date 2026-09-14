from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.core.connection import ConnectionManager, MavlinkConnection
from src.core.types import ConnectionEndpoint, ConnectionState


@pytest.fixture
def test_endpoint() -> ConnectionEndpoint:
    """Provide a standard test connection endpoint."""
    return ConnectionEndpoint(address="127.0.0.1", port=5770, protocol="tcp")


def test_connection_initial_state(test_endpoint: ConnectionEndpoint) -> None:
    """Verify MavlinkConnection begins in DISCONNECTED state."""
    conn = MavlinkConnection(test_endpoint)
    assert conn.state == ConnectionState.DISCONNECTED
    assert conn.last_heartbeat_time == 0.0
    assert conn.endpoint == test_endpoint


@pytest.mark.asyncio
@patch("src.core.connection.create_mav_connection")
async def test_connect_success(mock_create: MagicMock, test_endpoint: ConnectionEndpoint) -> None:
    """Verify successful connect transitions through CONNECTING."""
    mock_mav = MagicMock()
    mock_create.return_value = mock_mav

    conn = MavlinkConnection(test_endpoint)
    success = await conn.connect()

    assert success is True
    initial_state = conn.state
    assert initial_state == ConnectionState.CONNECTING
    await conn.disconnect()
    final_state = conn.state
    assert final_state == ConnectionState.DISCONNECTED


@pytest.mark.asyncio
@patch("src.core.connection.create_mav_connection", side_effect=OSError("Network unreachable"))
async def test_connect_failure(mock_create: MagicMock, test_endpoint: ConnectionEndpoint) -> None:
    """Verify failed connect transitions back to DISCONNECTED and returns False."""
    conn = MavlinkConnection(test_endpoint)
    success = await conn.connect()

    assert success is False
    assert conn.state == ConnectionState.DISCONNECTED


@pytest.mark.asyncio
async def test_process_heartbeat_transitions_to_connected(
    test_endpoint: ConnectionEndpoint,
) -> None:
    """Verify receiving a HEARTBEAT message transitions state to CONNECTED."""
    conn = MavlinkConnection(test_endpoint)
    states: list[ConnectionState] = []

    async def on_state(s: ConnectionState) -> None:
        states.append(s)

    conn.on_state_change(on_state)

    hb_msg = MagicMock()
    hb_msg.get_type.return_value = "HEARTBEAT"

    await conn._process_received_msg(hb_msg)

    assert conn.state == ConnectionState.CONNECTED
    assert conn.last_heartbeat_time > 0.0
    assert ConnectionState.CONNECTED in states


@pytest.mark.asyncio
async def test_message_handler_invoked(test_endpoint: ConnectionEndpoint) -> None:
    """Verify message handlers receive forwarded MAVLink messages."""
    conn = MavlinkConnection(test_endpoint)
    received: list[str] = []

    async def on_msg(msg: MagicMock) -> None:
        received.append(msg.get_type())

    conn.on_message(on_msg)

    msg = MagicMock()
    msg.get_type.return_value = "ATTITUDE"
    await conn._process_received_msg(msg)

    assert received == ["ATTITUDE"]


@pytest.mark.asyncio
@patch("src.core.connection.create_mav_connection")
async def test_connection_manager_lifecycle(
    mock_create: MagicMock,
    test_endpoint: ConnectionEndpoint,
) -> None:
    """Verify ConnectionManager add, get, list, and remove operations."""
    mgr = ConnectionManager()
    assert len(mgr.list_connections()) == 0

    conn = await mgr.add_connection(test_endpoint)
    assert conn.endpoint == test_endpoint
    assert mgr.get_connection(test_endpoint) is conn
    assert len(mgr.list_connections()) == 1

    await mgr.remove_connection(test_endpoint)
    assert mgr.get_connection(test_endpoint) is None
    assert len(mgr.list_connections()) == 0
