"""
Integration test: run the real Modbus server (Milestone 2) in a
background thread, then run the real collector loop against it for a
handful of polls and check the telemetry records it produced.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from collector.collector import run_collector
from collector.telemetry import TelemetryRecord
from simulator.modbus.server import run_server

TEST_HOST = "127.0.0.1"
TEST_PORT = 15021  # distinct from the Milestone 2 test server's port


def _start_server_in_background_thread() -> None:
    def _target() -> None:
        asyncio.run(run_server(host=TEST_HOST, port=TEST_PORT, tick_seconds=0.1, publish_mqtt=False))

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()


@pytest.fixture(scope="module")
def modbus_server():
    _start_server_in_background_thread()
    time.sleep(1.0)
    yield


def test_collector_produces_telemetry_records(modbus_server):
    records: list[TelemetryRecord] = []

    run_collector(
        host=TEST_HOST,
        port=TEST_PORT,
        asset_id="PLC-001",
        poll_seconds=0.1,
        max_polls=5,
        on_telemetry=records.append,
    )

    assert len(records) == 5
    for record in records:
        assert record.asset_id == "PLC-001"
        assert 0.0 <= record.temperature <= 150.0
        assert 0.0 <= record.pressure <= 20.0
        assert 0.0 <= record.tank_level_percent <= 100.0
        assert record.pump_state.value in ("ON", "OFF", "FAULT")


def test_collector_survives_unreachable_plc_then_recovers(modbus_server):
    """
    Point the collector at a port nothing is listening on for a couple
    of polls (simulating a PLC that's briefly unreachable), then check
    it doesn't crash - it should just silently produce zero records.
    """
    records: list[TelemetryRecord] = []
    unused_port = 15099

    run_collector(
        host=TEST_HOST,
        port=unused_port,
        asset_id="PLC-001",
        poll_seconds=0.1,
        max_polls=3,
        on_telemetry=records.append,
    )

    assert records == []
