"""
End-to-end proof that the Modbus server and the MQTT publisher agree:
the exact same Plant tick is visible through both protocols at once -
one via a Modbus read, the other via an MQTT message that just
arrives. Skips cleanly if Mosquitto isn't running, same pattern as
test_mqtt_publisher.py.
"""

from __future__ import annotations

import asyncio
import json
import socket
import threading
import time

import pytest
from pymodbus.client import ModbusTcpClient

from simulator.modbus import mapping
from simulator.modbus.server import run_server
from simulator.mqtt.payload import topic_for
from simulator.mqtt.publisher import DEFAULT_HOST as MQTT_HOST
from simulator.mqtt.publisher import DEFAULT_PORT as MQTT_PORT

TEST_HOST = "127.0.0.1"
TEST_PORT = 15021  # distinct from other test files' ports
# Deliberately NOT "PLC-001": that topic may already carry a retained
# message from a previous manual run (retain=True means a broker
# hands a brand-new subscriber the LAST message ever published to a
# topic, even from a completely different process). A dedicated test
# asset id keeps this test's first "fresh" message unambiguous.
TEST_ASSET_ID = "TEST-MODBUS-MQTT"
TICK_SECONDS = 3.0  # generous window: read Modbus right after an MQTT
# message arrives, comfortably before the NEXT tick could overwrite it


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

    received: list[dict] = []

    def _on_message(_client, _userdata, msg):
        received.append(json.loads(msg.payload))

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.on_message = _on_message
    subscriber.connect(MQTT_HOST, MQTT_PORT)
    subscriber.subscribe(topic_for(TEST_ASSET_ID))
    subscriber.loop_start()

    def _target() -> None:
        asyncio.run(
            run_server(
                host=TEST_HOST,
                port=TEST_PORT,
                tick_seconds=TICK_SECONDS,
                asset_id=TEST_ASSET_ID,
                publish_mqtt=True,
            )
        )

    thread = threading.Thread(target=_target, daemon=True)
    thread.start()

    try:
        # index 0 could be a stale retained message from a previous
        # run of this same test; index 1 can only be a fresh publish
        # from THIS server instance's first live tick.
        deadline = time.time() + 2 * TICK_SECONDS + 5
        while len(received) < 2 and time.time() < deadline:
            time.sleep(0.05)
        assert len(received) >= 2, "expected a fresh (non-retained) MQTT telemetry message"
        mqtt_reading = received[-1]

        modbus_client = ModbusTcpClient(TEST_HOST, port=TEST_PORT)
        assert modbus_client.connect()
        try:
            hr_response = modbus_client.read_holding_registers(
                address=mapping.HR_TEMPERATURE, count=mapping.HOLDING_REGISTER_COUNT
            )
            modbus_temperature = hr_response.registers[mapping.HR_TEMPERATURE] / mapping.SCALE
        finally:
            modbus_client.close()

        # Both protocols report the plant's temperature; MQTT payloads
        # round to 2 decimals (payload.py), Modbus rounds to the
        # nearest 0.01 via its integer SCALE factor (mapping.py) - so
        # a small tolerance covers both roundings without asserting
        # exact float equality.
        assert modbus_temperature == pytest.approx(mqtt_reading["temperature"], abs=0.02)
        assert mqtt_reading["asset_id"] == TEST_ASSET_ID
    finally:
        subscriber.loop_stop()
        subscriber.disconnect()
