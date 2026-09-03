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
from typing import Callable

from pymodbus.datastore import ModbusSequentialDataBlock, ModbusServerContext, ModbusSlaveContext
from pymodbus.server import StartAsyncTcpServer

from simulator.loop import Plant, PlantConfig
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

# Modbus function codes for the two WRITE request types pymodbus
# routes through ModbusSlaveContext.setValues(). Every OTHER caller of
# setValues() in this file (see _updater_loop below) always passes
# fc=3 or fc=1 - the "read" function codes, by pymodbus convention,
# even for our own internal updates - so these two values reliably
# identify a genuine externally-initiated write, never our own tick.
_WRITE_FUNCTION_CODES = (6, 16)

WriteCallback = Callable[[int, int, list], None]


class AuditingSlaveContext(ModbusSlaveContext):
    """
    A ModbusSlaveContext that reports genuine external WRITE requests
    (FC06 write single register, FC16 write multiple registers) to an
    on_write callback, then behaves exactly like the base class.

    Milestone 15: this is what makes a Modbus write audit-loggable at
    all - see detection/rules/suspicious_configuration_change.py's
    docstring, which named exactly this gap ("a write-audit path on
    the Modbus server, logging every FC06/16 request") as a
    prerequisite for that rule. on_write is generic (no DB/audit-log
    knowledge here - see simulator/mqtt/publisher.py and
    collector/persistence.py for the same "core module stays
    infrastructure-agnostic, a separate adapter supplies the real
    callback" pattern used throughout this project) so this class
    stays trivially testable with a plain Python list as the sink.
    """

    def __init__(self, *args, on_write: WriteCallback | None = None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._on_write = on_write

    def setValues(self, fc_as_hex: int, address: int, values: list) -> None:
        if self._on_write is not None and fc_as_hex in _WRITE_FUNCTION_CODES:
            self._on_write(fc_as_hex, address, values)
        super().setValues(fc_as_hex, address, values)


def build_context(on_write: WriteCallback | None = None) -> ModbusServerContext:
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

    slave_context = AuditingSlaveContext(
        hr=holding_registers,
        co=coils,
        zero_mode=True,
        on_write=on_write,
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
    on_write: WriteCallback | None = None,
    plant_config: PlantConfig | None = None,
) -> None:
    """
    Start the Modbus TCP server and the background plant-updater task
    together. Runs forever (StartAsyncTcpServer blocks until stopped),
    so this is meant to be the entry point of a long-running process.

    publish_mqtt=False (used by tests) skips even attempting an MQTT
    connection - MqttPublisher already tolerates an unreachable broker
    gracefully, but tests that don't care about MQTT at all shouldn't
    need Mosquitto running just to exercise the Modbus server.

    on_write=None by default (used by most tests) - no audit-log
    persistence happens unless the caller opts in, same reasoning as
    publish_mqtt=False.

    plant_config=None runs the plant with every default this project
    has used since Milestone 1 (see PlantConfig). Milestone 16
    (multi-asset) passes a different profile (PLANT_PROFILES in
    simulator/loop.py) so a second simulated asset is a genuinely
    different process, not PLC-001 running on a different port.
    """
    context = build_context(on_write=on_write)
    plant = Plant(plant_config)

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
    import os

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    # Milestone 16 (multi-asset): every knob a second instance of this
    # process needs is an env var with a default that reproduces
    # Milestone 1-15's single-asset behavior exactly, so `python -m
    # simulator.modbus.server` with no environment configured is
    # unchanged. Running a second simulated PLC is then just:
    #   MODBUS_ASSET_ID=PLC-002 MODBUS_PORT=5021 PLANT_PROFILE=cooling-loop \
    #     python -m simulator.modbus.server
    asset_id = os.environ.get("MODBUS_ASSET_ID", DEFAULT_ASSET_ID)
    host = os.environ.get("MODBUS_HOST", DEFAULT_HOST)
    port = int(os.environ.get("MODBUS_PORT", str(DEFAULT_PORT)))
    profile_name = os.environ.get("PLANT_PROFILE", "default")
    try:
        from simulator.loop import PLANT_PROFILES

        plant_config = PLANT_PROFILES[profile_name]
    except KeyError:
        raise SystemExit(
            f"Unknown PLANT_PROFILE '{profile_name}' - choices: {', '.join(PLANT_PROFILES)}"
        )

    # Local import so this module stays importable/testable without a
    # database - same discipline as collector.py's __main__ (see its
    # comment for why). record_modbus_write is the only piece of this
    # file that ever touches Postgres.
    from simulator.modbus.audit import record_modbus_write

    def _on_write(fc: int, address: int, values: list) -> None:
        record_modbus_write(asset_id, fc, address, values)

    asyncio.run(
        run_server(host=host, port=port, asset_id=asset_id, plant_config=plant_config, on_write=_on_write)
    )
