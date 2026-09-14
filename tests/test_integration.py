from __future__ import annotations

import asyncio
import time
from typing import Any

import pytest

from src.core.protocol import (
    create_mav_connection,
    create_param_request_list_msg,
    create_rc_override_msg,
)
from src.core.types import ConnectionEndpoint
from src.simulators.rover_config import DEFAULT_ROVER_CONFIG
from src.simulators.rover_physics import RoverKinematics
from src.simulators.rover_sim import RoverMavlinkServer


@pytest.mark.asyncio
async def test_rover_sim_sends_heartbeat() -> None:
    """End-to-end: RoverMavlinkServer broadcasts HEARTBEAT over TCP."""
    test_port = 5780
    kin = RoverKinematics(DEFAULT_ROVER_CONFIG)
    server = RoverMavlinkServer(kin, DEFAULT_ROVER_CONFIG, port=test_port)
    await server.start()

    endpoint = ConnectionEndpoint(address="127.0.0.1", port=test_port, protocol="tcp")
    mav_conn = create_mav_connection(endpoint)

    try:
        hb_received = False
        start = time.time()
        while time.time() - start < 3.0:
            msg = mav_conn.recv_msg()
            if msg and msg.get_type() == "HEARTBEAT":
                assert msg.type == 10  # MAV_TYPE_GROUND_ROVER
                assert msg.autopilot == 0  # MAV_AUTOPILOT_GENERIC
                hb_received = True
                break
            await asyncio.sleep(0.05)
        assert hb_received is True
    finally:
        mav_conn.close()
        await server.stop()


@pytest.mark.asyncio
async def test_rover_sim_responds_to_param_request() -> None:
    """End-to-end: Rover responds to PARAM_REQUEST_LIST with 19 parameters."""
    test_port = 5781
    kin = RoverKinematics(DEFAULT_ROVER_CONFIG)
    server = RoverMavlinkServer(kin, DEFAULT_ROVER_CONFIG, port=test_port)
    await server.start()

    endpoint = ConnectionEndpoint(address="127.0.0.1", port=test_port, protocol="tcp")
    mav_conn = create_mav_connection(endpoint)

    try:
        # Wait for initial heartbeat
        start = time.time()
        while time.time() - start < 3.0:
            msg = mav_conn.recv_msg()
            if msg and msg.get_type() == "HEARTBEAT":
                break
            await asyncio.sleep(0.05)

        # Send request
        req = create_param_request_list_msg(target_system=2, target_component=1)
        mav_conn.mav.send(req)

        param_values: list[Any] = []
        start = time.time()
        while time.time() - start < 4.0:
            msg = mav_conn.recv_msg()
            if msg and msg.get_type() == "PARAM_VALUE":
                param_values.append(msg)
                if len(param_values) >= 19:
                    break
            await asyncio.sleep(0.05)

        assert len(param_values) == 19
    finally:
        mav_conn.close()
        await server.stop()


@pytest.mark.asyncio
async def test_rc_override_changes_rover_state() -> None:
    """End-to-end: RC_CHANNELS_OVERRIDE updates rover server PWM state."""
    test_port = 5782
    kin = RoverKinematics(DEFAULT_ROVER_CONFIG)
    server = RoverMavlinkServer(kin, DEFAULT_ROVER_CONFIG, port=test_port)
    await server.start()

    endpoint = ConnectionEndpoint(address="127.0.0.1", port=test_port, protocol="tcp")
    mav_conn = create_mav_connection(endpoint)

    try:
        # Wait for heartbeat
        start = time.time()
        while time.time() - start < 3.0:
            msg = mav_conn.recv_msg()
            if msg and msg.get_type() == "HEARTBEAT":
                break
            await asyncio.sleep(0.05)

        # Send RC override: steering=1300, throttle=1700
        override = create_rc_override_msg(
            target_system=2,
            target_component=1,
            throttle=1700,
            steering=1300,
        )
        mav_conn.mav.send(override)

        # Poll until server reflects state
        start = time.time()
        while time.time() - start < 2.0:
            if server.current_rc == (1700, 1300):
                break
            await asyncio.sleep(0.05)

        assert server.current_rc == (1700, 1300)
    finally:
        mav_conn.close()
        await server.stop()
