"""
Pure JSON-payload construction for MQTT telemetry publishing - kept
separate from the paho-mqtt client wrapper (publisher.py) for the same
reason simulator/modbus/mapping.py is separate from server.py: the
actual engineering decision (what goes in the message, how it's
shaped) should be unit-testable without a running broker.

--- Why MQTT payloads don't need mapping.py's scaling tricks ---

Modbus holding registers are fixed-width 16-bit unsigned integers, so
mapping.py has to multiply floats by a SCALE factor to fit the wire
format, and the reader has to know to divide back out. MQTT has no
such constraint - a message is just an arbitrary byte payload, and
JSON natively represents floats, strings, and booleans as themselves.
This is a concrete, visible illustration of "modern protocol vs.
legacy protocol": MQTT's flexibility eliminates an entire category of
encoding decisions (and an entire category of encoding BUGS - a wrong
SCALE constant would silently corrupt every value) that Modbus forces
on every register.
"""

from __future__ import annotations

import json

from simulator.plc.plc import PLCDecision, PLCReadings

TOPIC_TEMPLATE = "forgesentinel/{asset_id}/telemetry"


def topic_for(asset_id: str) -> str:
    return TOPIC_TEMPLATE.format(asset_id=asset_id)


def build_payload(
    asset_id: str,
    readings: PLCReadings,
    decision: PLCDecision,
    timestamp: str,
) -> str:
    """
    Build the JSON string published to MQTT on each simulator tick.
    Mirrors the same fields Modbus exposes (see mapping.py) plus
    asset_id/timestamp, which MQTT payloads carry inline since -
    unlike Modbus registers - there's no separate addressing scheme
    that already identifies "which device, which moment" for us.
    """
    body = {
        "asset_id": asset_id,
        "timestamp": timestamp,
        "temperature": round(readings.temperature, 2),
        "pressure": round(readings.pressure, 2),
        "tank_level_percent": round(readings.tank_level_percent, 2),
        "pump_state": readings.pump_state.value,
        "cooling_active": decision.cooling_active,
        "inlet_open": decision.inlet_open,
    }
    return json.dumps(body)
