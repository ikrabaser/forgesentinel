"""
Confirms the collector actually increments forgesentinel_modbus_
requests_total / forgesentinel_collector_errors_total while running,
using the same real-server integration pattern as test_collector.py.

Counters are read via .collect() (the public API) rather than the
private ._value attribute. They're process-lifetime globals in
collector/metrics.py, so tests compare a before/after delta rather
than asserting an absolute value - other tests importing the same
module elsewhere in the suite may have already incremented them.
"""

from __future__ import annotations

import asyncio
import threading
import time

import pytest

from collector.collector import run_collector
from collector.metrics import COLLECTOR_ERRORS_TOTAL, MODBUS_REQUESTS_TOTAL
from simulator.modbus.server import run_server

TEST_HOST = "127.0.0.1"
TEST_PORT = 15022  # distinct from other test files' ports


def _counter_value(counter) -> float:
    return counter.collect()[0].samples[0].value


@pytest.fixture(scope="module")
def modbus_server():
    def _target() -> None:
        asyncio.run(run_server(host=TEST_HOST, port=TEST_PORT, tick_seconds=0.1, publish_mqtt=False))

    threading.Thread(target=_target, daemon=True).start()
    time.sleep(1.0)
    yield


def test_successful_polls_increment_modbus_requests_total(modbus_server):
    before = _counter_value(MODBUS_REQUESTS_TOTAL)

    run_collector(
        host=TEST_HOST, port=TEST_PORT, poll_seconds=0.1, max_polls=5, on_telemetry=lambda r: None
    )

    assert _counter_value(MODBUS_REQUESTS_TOTAL) == before + 5


def test_unreachable_plc_increments_collector_errors_total():
    before = _counter_value(COLLECTOR_ERRORS_TOTAL)
    unused_port = 15098

    run_collector(
        host=TEST_HOST,
        port=unused_port,
        poll_seconds=0.1,
        max_polls=3,
        on_telemetry=lambda r: None,
    )

    assert _counter_value(COLLECTOR_ERRORS_TOTAL) == before + 3
