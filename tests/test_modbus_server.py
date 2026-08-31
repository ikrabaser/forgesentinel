"""
Integration test: actually starts the Modbus TCP server on localhost
and reads it back with a real Modbus client over a real (loopback)
socket. This is deliberately heavier than the unit tests in
test_modbus_mapping.py - it proves the wiring (server <-> datastore
<-> updater loop) works end to end, not just the pure math.

We run the server in a background thread (with its own asyncio event
loop) rather than using pytest-asyncio, to keep this test independent
of any async test-runner configuration.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest
from pymodbus.client import ModbusTcpClient

from simulator.modbus import mapping
from simulator.modbus.server import run_server

TEST_HOST = "127.0.0.1"
TEST_PORT = 15020  # distinct from the default 5020 to avoid clashing
# with a manually-started server during local development.


def _start_server_in_background_thread() -> None:
    def _target() -> None:
        asyncio.run(run_server(host=TEST_HOST, port=TEST_PORT, tick_seconds=0.1, publish_mqtt=False))

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()


@pytest.fixture(scope="module")
def modbus_server():
    _start_server_in_background_thread()
    # Give the server a moment to bind its socket and the updater loop
    # a moment to write its first tick of values.
    time.sleep(1.0)
    yield
    # Daemon thread - dies automatically when the test process exits.


def test_holding_registers_are_reachable_and_plausible(modbus_server):
    client = ModbusTcpClient(TEST_HOST, port=TEST_PORT)
    try:
        assert client.connect(), "could not connect to Modbus TCP server"

        result = client.read_holding_registers(
            address=0, count=mapping.HOLDING_REGISTER_COUNT, slave=1
        )
        assert not result.isError()

        temperature = mapping.decode_scaled(result.registers[mapping.HR_TEMPERATURE])
        pressure = mapping.decode_scaled(result.registers[mapping.HR_PRESSURE])
        tank_level_percent = mapping.decode_scaled(result.registers[mapping.HR_TANK_LEVEL])
        pump_state = mapping.decode_pump_state(result.registers[mapping.HR_PUMP_STATE])

        # We don't know the exact tick the server is on, but the plant's
        # physical bounds must always hold - this is what actually
        # proves the Modbus layer is faithfully mirroring real Plant
        # state rather than returning garbage/zeros.
        assert 0.0 <= temperature <= 150.0
        assert 0.0 <= pressure <= 20.0
        assert 0.0 <= tank_level_percent <= 100.0
        assert pump_state.value in ("ON", "OFF", "FAULT")
    finally:
        client.close()


def test_coils_are_reachable_and_boolean(modbus_server):
    client = ModbusTcpClient(TEST_HOST, port=TEST_PORT)
    try:
        assert client.connect(), "could not connect to Modbus TCP server"

        result = client.read_coils(address=0, count=mapping.COIL_COUNT, slave=1)
        assert not result.isError()
        assert len(result.bits) >= mapping.COIL_COUNT
        assert isinstance(result.bits[mapping.COIL_COOLING_ACTIVE], bool)
        assert isinstance(result.bits[mapping.COIL_INLET_OPEN], bool)
    finally:
        client.close()


def test_values_change_over_time(modbus_server):
    """
    The updater loop ticks every 0.1s in this test config. Reading
    twice with a gap should show the register block actually being
    refreshed, not written once and left static.
    """
    client = ModbusTcpClient(TEST_HOST, port=TEST_PORT)
    try:
        assert client.connect()

        first = client.read_holding_registers(
            address=0, count=mapping.HOLDING_REGISTER_COUNT, slave=1
        )
        time.sleep(0.5)
        second = client.read_holding_registers(
            address=0, count=mapping.HOLDING_REGISTER_COUNT, slave=1
        )

        assert not first.isError() and not second.isError()
        # At least one of the tracked values should differ after half
        # a second of ticking (tank level moves every tick in our sim).
        assert first.registers != second.registers
    finally:
        client.close()
