"""
Modbus TCP server: exposes PLC-001's simulated state over the network
using the industry-standard Modbus TCP protocol.

Real-world analogy:
    In a real plant, the PLC itself runs a Modbus TCP *server* (older
    terminology: "slave") on its network interface. Other systems -
    a SCADA/HMI system, an engineering workstation, or (later in this
    project) our own telemetry collector - act as Modbus *clients*
    ("masters") that connect and read/write registers over the
    network. We are simulating exactly that role: this process stands
    in for the PLC's network-facing side.

What this file does NOT do:
    It does not run the plant's control logic over the network - the
    Plant/PLCController from Milestone 1 still run locally, in-process,
    each tick. This server only *mirrors* the resulting state into
    Modbus registers/coils so other processes can observe it the same
    way they would observe a real PLC. Later (telemetry collector
    milestone) we'll build a separate client process that reads from
    here instead of importing simulator code directly - that mirrors
    how a real collector never gets to "cheat" by importing the PLC's
    internal Python objects.

Milestone 13: this same process ALSO publishes every tick over MQTT
(simulator/mqtt/), so the exact same Plant/PLCController state reaches
the outside world through two fundamentally different protocol
philosophies at once - Modbus's pull ("ask me and I'll answer") and
MQTT's push ("I'll tell you the moment something changes"). Real
multi-protocol gateways commonly do exactly this: one physical device,
several network-facing personalities for different kinds of consumer.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer

from simulator.loop import Plant
from simulator.modbus import mapping
from simulator.mqtt.payload import build_payload, topic_for
from simulator.mqtt.publisher import MqttPublisher

logger = logging.getLogger("forgesentinel.modbus_server")

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 5020  # 502 is the standard Modbus port but requires
# elevated/admin privileges on most OSes; 5020 is the common
# unprivileged substitute used for local development and testing.
DEFAULT_TICK_SECONDS = 1.0
DEFAULT_ASSET_ID = "PLC-001"


def build_context() -> ModbusServerContext:
    """
    Build an empty Modbus datastore sized to our register/coil map.

    zero_mode=True: addresses passed to this datastore's API (and the
    ones a Modbus client sends over the wire) are used directly as
    zero-based protocol addresses - see the long comment in
    mapping.py for why we're explicit about this instead of leaving
    it to pymodbus's default (which applies a +1 offset, matching the
    legacy human-readable convention instead of the raw protocol).
    """
    holding_registers = ModbusSequentialDataBlock(0, [0] * mapping.HOLDING_REGISTER_COUNT)
    coils = ModbusSequentialDataBlock(0, [False] * mapping.COIL_COUNT)

    slave_context = ModbusSlaveContext(
        hr=holding_registers,
        co=coils,
        zero_mode=True,
    )
    # single=True: we're simulating exactly one PLC on this server, so
    # every incoming request is answered by the same device context
    # regardless of the Modbus "unit/slave id" the client sends.
    return ModbusServerContext(slaves=slave_context, single=True)


async def _updater_loop(
    context: ModbusServerContext,
    plant: Plant,
    tick_seconds: float,
    mqtt_publisher: MqttPublisher | None = None,
    asset_id: str = DEFAULT_ASSET_ID,
) -> None:
    """
    Background task: advance the Plant one tick, then write the
    resulting state into the Modbus datastore AND (if configured)
    publish it to MQTT. Runs forever until cancelled.

    This runs in the same asyncio event loop as the Modbus server
    itself, so there's no race condition between "the plant is being
    updated" and "a client request is being answered" - asyncio only
    runs one coroutine at a time, so each of these operations
    completes atomically with respect to the other. The MQTT publish
    call is non-blocking (paho-mqtt hands the message to its own
    background thread - see publisher.py), so it doesn't stall this
    loop even if the broker is momentarily slow to acknowledge.
    """
    device = context[0]  # single=True -> device id 0 is our one PLC
    while True:
        readings = plant.step()
        decision = plant.last_decision
        assert decision is not None  # step() always sets it

        holding_values = mapping.build_holding_registers(
            temperature=readings.temperature,
            pressure=readings.pressure,
            tank_level_percent=readings.tank_level_percent,
            pump_state=readings.pump_state,
        )
        coil_values = mapping.build_coils(
            cooling_active=decision.cooling_active,
            inlet_open=decision.inlet_open,
        )

        # Function code 3 = holding registers, function code 1 = coils.
        # (pymodbus datastore convention: use the "read" function code
        # to address a table regardless of read vs write.)
        device.setValues(3, mapping.HR_TEMPERATURE, holding_values)
        device.setValues(1, mapping.COIL_COOLING_ACTIVE, coil_values)

        if mqtt_publisher is not None:
            payload = build_payload(
                asset_id=asset_id,
                readings=readings,
                decision=decision,
                timestamp=datetime.now(timezone.utc).isoformat(),
            )
            mqtt_publisher.publish(topic_for(asset_id), payload)

        logger.info(
            "tick=%03d level=%5.1f%% temp=%6.2fC pressure=%5.2fbar pump=%s cooling=%s inlet=%s",
            plant.tick_count,
            readings.tank_level_percent,
            readings.temperature,
            readings.pressure,
            readings.pump_state.value,
            decision.cooling_active,
            decision.inlet_open,
        )

        await asyncio.sleep(tick_seconds)


async def run_server(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    tick_seconds: float = DEFAULT_TICK_SECONDS,
    asset_id: str = DEFAULT_ASSET_ID,
    publish_mqtt: bool = True,
) -> None:
    """
    Start the Modbus TCP server and the background plant-updater task
    together. Runs forever (StartAsyncTcpServer blocks until stopped),
    so this is meant to be the entry point of a long-running process.

    publish_mqtt=False (used by tests) skips even attempting an MQTT
    connection - MqttPublisher already tolerates an unreachable broker
    gracefully, but tests that don't care about MQTT at all shouldn't
    need Mosquitto running just to exercise the Modbus server.
    """
    context = build_context()
    plant = Plant()

    mqtt_publisher: MqttPublisher | None = None
    if publish_mqtt:
        mqtt_publisher = MqttPublisher(client_id=f"forgesentinel-{asset_id.lower()}")
        mqtt_publisher.connect()

    updater_task = asyncio.create_task(
        _updater_loop(context, plant, tick_seconds, mqtt_publisher, asset_id)
    )
    logger.info("ForgeSentinel Modbus TCP server starting on %s:%d", host, port)
    try:
        await StartAsyncTcpServer(context=context, address=(host, port))
    finally:
        updater_task.cancel()
        if mqtt_publisher is not None:
            mqtt_publisher.close()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(run_server())
