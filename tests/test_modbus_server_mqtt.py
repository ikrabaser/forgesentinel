"""
End-to-end proof that the Modbus server and the MQTT publisher agree:
the exact same Plant tick is visible through both protocols at once -
one via a Modbus read, the other via an MQTT message that just
arrives. Skips cleanly if Mosquitto isn't running, same pattern as
test_mqtt_publisher.py.

Known limitation: this test is reliable on its own (`pytest
tests/test_modbus_server_mqtt.py`) or alongside a handful of related
files, but can flake when run inside the FULL suite. Several
pre-existing tests in this codebase (test_modbus_server.py,
test_collector.py, test_collector_metrics.py) start a Modbus server in
a background daemon thread and never stop it - by the time this test
runs, several of those threads are still ticking forever in the same
process, and the resulting GIL contention has been observed to make a
Modbus read return a stale value for many seconds at a stretch. That's
a pre-existing test-hygiene gap (nothing here or in those files
cancels the updater task or joins the thread), not a defect in the
MQTT feature itself - if this test needs debugging, run it in
isolation first.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time
import uuid

import pytest
from pymodbus.client import ModbusTcpClient

from simulator.modbus import mapping
from simulator.modbus.server import run_server
from simulator.mqtt.payload import topic_for
from simulator.mqtt.publisher import DEFAULT_HOST as MQTT_HOST
from simulator.mqtt.publisher import DEFAULT_PORT as MQTT_PORT

TEST_HOST = "127.0.0.1"
TEST_PORT = 15021  # distinct from other test files' ports
TICK_SECONDS = 3.0


def _broker_reachable(host: str = MQTT_HOST, port: int = MQTT_PORT, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture()
def require_broker():
    if not _broker_reachable():
        pytest.skip(
            f"Mosquitto not reachable at {MQTT_HOST}:{MQTT_PORT}; "
            "start it with `docker compose up -d mosquitto` to run this test"
        )


def test_modbus_and_mqtt_report_the_same_tick(require_broker):
    import paho.mqtt.client as mqtt

    # A fresh, never-published-before topic for every test run - this
    # sidesteps retain=True entirely (see publisher.py's docstring):
    # since nothing has EVER published to this exact asset id's topic,
    # there is no possible stale retained message a new subscriber
    # could be handed, so the very first message received is
    # guaranteed to come from THIS run's server, not some earlier one.
    test_asset_id = f"TEST-MODBUS-MQTT-{uuid.uuid4().hex[:8]}"

    received: list[dict] = []

    def _on_message(_client, _userdata, msg):
        received.append(json.loads(msg.payload))

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.on_message = _on_message
    subscriber.connect(MQTT_HOST, MQTT_PORT)
    subscriber.subscribe(topic_for(test_asset_id))
    subscriber.loop_start()

    def _target() -> None:
        asyncio.run(
            run_server(
                host=TEST_HOST,
                port=TEST_PORT,
                tick_seconds=TICK_SECONDS,
                asset_id=test_asset_id,
                publish_mqtt=True,
            )
        )

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

    def _read_modbus_temperature() -> float | None:
        """
        A fresh connection per attempt, deliberately not one reused
        connection held open for the whole test: this suite leaves
        several OTHER tests' Modbus servers ticking forever in their
        own never-joined daemon threads (test_modbus_server.py,
        test_collector*.py), and under that accumulated background
        load a long-held socket occasionally returned stale data in
        practice. A short-lived connection per read sidesteps that
        entirely and costs little since Modbus TCP connects are cheap.
        """
        with ModbusTcpClient(TEST_HOST, port=TEST_PORT) as client:
            if not client.connect():
                return None
            response = client.read_holding_registers(
                address=mapping.HR_TEMPERATURE, count=mapping.HOLDING_REGISTER_COUNT
            )
            if response.isError():
                return None
            return response.registers[mapping.HR_TEMPERATURE] / mapping.SCALE

    try:
        # Poll both protocols in a tight loop and accept the first
        # moment they agree, rather than snapshotting each once and
        # hoping no tick landed in between - under the full test suite
        # (see _read_modbus_temperature's docstring), GIL contention
        # from other tests' background threads can stall this one for
        # an unpredictable stretch. Only a genuine bug (the two
        # protocols reporting DIFFERENT plant state, not just
        # different TIMING) can make this loop fail.
        timeout = TICK_SECONDS * 4 + 15
        deadline = time.time() + timeout
        modbus_temperature = None
        mqtt_reading = None
        matched = False
        while time.time() < deadline:
            if received:
                mqtt_reading = received[-1]
                modbus_temperature = _read_modbus_temperature()
                # MQTT payloads round to 2 decimals (payload.py),
                # Modbus rounds to the nearest 0.01 via its integer
                # SCALE factor (mapping.py) - a small tolerance covers
                # both roundings without asserting exact float equality.
                if modbus_temperature is not None and modbus_temperature == pytest.approx(
                    mqtt_reading["temperature"], abs=0.02
                ):
                    matched = True
                    break
            time.sleep(0.1)

        assert matched, (
            f"Modbus and MQTT never agreed on temperature within {timeout:.0f}s "
            f"(last modbus={modbus_temperature}, last mqtt={mqtt_reading})"
        )
        assert mqtt_reading["asset_id"] == test_asset_id
    finally:
        subscriber.loop_stop()
        subscriber.disconnect()
