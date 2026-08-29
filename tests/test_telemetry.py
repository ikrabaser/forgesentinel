from datetime import datetime, timezone

import pytest

from collector.telemetry import decode_telemetry
from simulator.modbus import mapping
from simulator.process.pump import PumpState


def make_raw(temperature=90.0, pressure=2.5, level=50.0, pump=PumpState.ON, cooling=True, inlet=False):
    registers = mapping.build_holding_registers(
        temperature=temperature, pressure=pressure, tank_level_percent=level, pump_state=pump
    )
    coils = mapping.build_coils(cooling_active=cooling, inlet_open=inlet)
    return registers, coils


def test_decode_telemetry_maps_all_fields():
    registers, coils = make_raw(
        temperature=91.5, pressure=3.2, level=64.0, pump=PumpState.ON, cooling=True, inlet=False
    )
    ts = datetime(2026, 1, 1, tzinfo=timezone.utc)

    record = decode_telemetry(
        asset_id="PLC-001", holding_registers=registers, coils=coils, timestamp=ts
    )

    assert record.asset_id == "PLC-001"
    assert record.timestamp == ts
    assert record.temperature == pytest.approx(91.5)
    assert record.pressure == pytest.approx(3.2)
    assert record.tank_level_percent == pytest.approx(64.0)
    assert record.pump_state == PumpState.ON
    assert record.cooling_active is True
    assert record.inlet_open is False


def test_decode_telemetry_defaults_timestamp_to_now():
    registers, coils = make_raw()
    before = datetime.now(timezone.utc)
    record = decode_telemetry(asset_id="PLC-001", holding_registers=registers, coils=coils)
    after = datetime.now(timezone.utc)
    assert before <= record.timestamp <= after


def test_decode_telemetry_rejects_short_register_block():
    registers, coils = make_raw()
    with pytest.raises(ValueError):
        decode_telemetry(asset_id="PLC-001", holding_registers=registers[:2], coils=coils)


def test_decode_telemetry_rejects_short_coil_block():
    registers, coils = make_raw()
    with pytest.raises(ValueError):
        decode_telemetry(asset_id="PLC-001", holding_registers=registers, coils=coils[:0])


def test_decode_telemetry_pump_fault_state():
    registers, coils = make_raw(pump=PumpState.FAULT)
    record = decode_telemetry(asset_id="PLC-001", holding_registers=registers, coils=coils)
    assert record.pump_state == PumpState.FAULT
