"""
MqttPublisher: thin wrapper around paho-mqtt for publishing plant
telemetry - the "push" counterpart to the Modbus server's "pull"
model. See payload.py for the actual message shape; this file only
owns the broker connection.

--- Push (MQTT) vs. pull (Modbus) ---

The Modbus server (simulator/modbus/server.py) never initiates
anything - it sits and waits for a client to ask. Every value a
Modbus client has is only ever as fresh as its last poll. MQTT
inverts that: the PLC (publisher, here) pushes a message the instant
new data exists, and any number of subscribers receive it without
ever asking. Neither model is strictly "better" - polling gives a
client full control over its own load and works over a direct
connection with no third party involved, while push scales better to
many simultaneous listeners and delivers lower latency - but seeing
both implemented against the exact same underlying Plant makes the
trade-off concrete rather than theoretical.

--- Why retain=True ---

MQTT brokers can "retain" the last message published to a topic and
immediately deliver it to any NEW subscriber the moment they connect,
even long after that message was originally sent. Modbus has no
equivalent - a first-time Modbus client must actively poll to learn
the current value; there is no "catch me up" built into the protocol.
retain=True here means a dashboard subscribing to our topic sees the
current plant state immediately on connect, not just from the next
tick onward.

--- Why QoS 1, not 0 or 2 ---

MQTT defines three Quality-of-Service levels:
    QoS 0: fire-and-forget - a message can be silently lost.
    QoS 1: at-least-once - guaranteed delivery, but a message can
           arrive duplicated (the sender resends if it doesn't see an
           acknowledgment in time, even if the original actually did
           arrive).
    QoS 2: exactly-once - guaranteed, no duplicates, but needs a
           4-step handshake per message, the highest overhead.
Telemetry that arrives duplicated is harmless here (a fresh tick's
value supersedes it a second later), but telemetry that's silently
lost is a real gap in the record. QoS 1 buys the delivery guarantee
we actually need without paying for QoS 2's extra handshake, which
would protect against a failure mode (duplicates) we don't care about.

--- Why connection failure doesn't crash the caller ---

A real PLC keeps controlling its physical process whether or not
anyone happens to be listening on its network interfaces. connect()
here logs a warning and leaves the publisher in a disconnected state
rather than raising, and publish() then becomes a silent no-op - the
same "never let an observability path take down the thing it's
observing" principle the collector and detection persistence layers
already follow elsewhere in this codebase.
"""

from __future__ import annotations

import logging

import paho.mqtt.client as mqtt

logger = logging.getLogger("forgesentinel.mqtt_publisher")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 1883  # Mosquitto's standard unencrypted listener port


class MqttPublisher:
    def __init__(
        self,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        client_id: str = "forgesentinel-plc-001",
    ) -> None:
        self._client = mqtt.Client(
            mqtt.CallbackAPIVersion.VERSION2, client_id=client_id
        )
        self._host = host
        self._port = port
        self._connected = False

    def connect(self) -> None:
        try:
            self._client.connect(self._host, self._port)
            self._client.loop_start()  # background thread handling the network I/O
            self._connected = True
            logger.info("MQTT publisher connected to %s:%d", self._host, self._port)
        except OSError as exc:
            self._connected = False
            logger.warning(
                "MQTT broker unreachable at %s:%d (%s); publishing disabled for this run",
                self._host,
                self._port,
                exc,
            )

    def publish(self, topic: str, payload: str) -> None:
        if not self._connected:
            return
        self._client.publish(topic, payload, qos=1, retain=True)

    def close(self) -> None:
        if self._connected:
            self._client.loop_stop()
            self._client.disconnect()
            self._connected = False
