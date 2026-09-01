import json

from simulator.mqtt.payload import build_payload, topic_for
from simulator.plc.plc import PLCDecision, PLCReadings
from simulator.process.pump import PumpState


def test_topic_for_includes_asset_id():
    assert topic_for("PLC-001") == "forgesentinel/PLC-001/telemetry"


def test_build_payload_shape_and_rounding():
    readings = PLCReadings(
        tank_level_percent=29.03219,
        temperature=87.61984,
        pressure=2.50501,
        pump_state=PumpState.ON,
    )
    decision = PLCDecision(pump_command=PumpState.ON, cooling_active=False, inlet_open=True)

    raw = build_payload("PLC-001", readings, decision, timestamp="2026-01-01T00:00:00Z")
    body = json.loads(raw)

    assert body == {
        "asset_id": "PLC-001",
        "timestamp": "2026-01-01T00:00:00Z",
        "temperature": 87.62,
        "pressure": 2.51,
        "tank_level_percent": 29.03,
        "pump_state": "ON",
        "cooling_active": False,
        "inlet_open": True,
    }


def test_build_payload_is_valid_json_for_every_pump_state():
    decision = PLCDecision(pump_command=PumpState.FAULT, cooling_active=True, inlet_open=False)
    for pump_state in PumpState:
        readings = PLCReadings(
            tank_level_percent=50.0, temperature=60.0, pressure=1.5, pump_state=pump_state
        )
        raw = build_payload("PLC-001", readings, decision, timestamp="2026-01-01T00:00:00Z")
        assert json.loads(raw)["pump_state"] == pump_state.value
