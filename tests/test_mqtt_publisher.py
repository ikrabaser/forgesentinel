"""
Integration test for MqttPublisher against a real Mosquitto broker.

Same pattern as tests/conftest.py's test_engine fixture for Postgres:
if the broker isn't reachable, skip rather than fail - a developer
without `docker compose up -d mosquitto` running shouldn't see a red
test for infrastructure they haven't started.
"""

from __future__ import annotations

import json
import socket
import time
import uuid

import pytest

from simulator.mqtt.payload import topic_for
from simulator.mqtt.publisher import DEFAULT_HOST, DEFAULT_PORT, MqttPublisher


def _broker_reachable(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT, timeout: float = 1.0) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


@pytest.fixture()
def require_broker():
    if not _broker_reachable():
        pytest.skip(
            f"Mosquitto not reachable at {DEFAULT_HOST}:{DEFAULT_PORT}; "
            "start it with `docker compose up -d mosquitto` to run this test"
        )


def test_publish_is_received_by_a_real_subscriber(require_broker):
    import paho.mqtt.client as mqtt

    # Unique per run: publish() sets retain=True, so a FIXED topic
    # would hand a new subscriber the previous test run's retained
    # message the instant it subscribes, before our own fresh publish
    # even happens - the exact bug this once produced two identical
    # {"hello": "world"} messages instead of one.
    topic = topic_for(f"TEST-ASSET-{uuid.uuid4().hex[:8]}")

    received: list[dict] = []

    def _on_message(_client, _userdata, msg):
        received.append(json.loads(msg.payload))

    subscriber = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2)
    subscriber.on_message = _on_message
    subscriber.connect(DEFAULT_HOST, DEFAULT_PORT)
    subscriber.subscribe(topic)
    subscriber.loop_start()
    try:
        publisher = MqttPublisher(client_id="forgesentinel-test-publisher")
        publisher.connect()
        publisher.publish(topic, json.dumps({"hello": "world"}))

        deadline = time.time() + 3
        while not received and time.time() < deadline:
            time.sleep(0.05)

        publisher.close()
    finally:
        subscriber.loop_stop()
        subscriber.disconnect()

    assert received == [{"hello": "world"}]


def test_publish_before_connect_is_a_silent_noop():
    # No broker required for this one: publisher was never connect()ed,
    # so publish() must not raise even though nothing will be sent.
    publisher = MqttPublisher(client_id="forgesentinel-test-unconnected")
    publisher.publish(topic_for("TEST-ASSET"), json.dumps({"hello": "world"}))


def test_connect_to_unreachable_broker_does_not_raise():
    # Port 1 is reserved and nothing should ever be listening there -
    # connect() must log and continue, never crash the caller.
    publisher = MqttPublisher(host="127.0.0.1", port=1, client_id="forgesentinel-test-unreachable")
    publisher.connect()
    publisher.publish(topic_for("TEST-ASSET"), json.dumps({"hello": "world"}))
