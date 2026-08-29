import pytest

from simulator.modbus import mapping
from simulator.process.pump import PumpState


def test_encode_decode_scaled_round_trip():
    raw = mapping.encode_scaled(87.62)
    assert raw == 8762
    assert mapping.decode_scaled(raw) == pytest.approx(87.62)


def test_encode_scaled_clamps_to_uint16_range():
    assert mapping.encode_scaled(-5.0) == 0  # never below 0
    assert mapping.encode_scaled(1000.0) == mapping.UINT16_MAX  # 1000*100 overflows 16 bits


def test_encode_scaled_zero():
    assert mapping.encode_scaled(0.0) == 0


@pytest.mark.parametrize(
    "state,code",
    [
        (PumpState.OFF, 0),
        (PumpState.ON, 1),
        (PumpState.FAULT, 2),
    ],
)
def test_pump_state_encode_decode_round_trip(state, code):
    assert mapping.encode_pump_state(state) == code
    assert mapping.decode_pump_state(code) == state


def test_decode_pump_state_rejects_unknown_code():
    with pytest.raises(ValueError):
        mapping.decode_pump_state(99)


def test_build_holding_registers_addresses_match_layout():
    registers = mapping.build_holding_registers(
        temperature=90.0,
        pressure=2.5,
        tank_level_percent=50.0,
        pump_state=PumpState.ON,
    )
    assert len(registers) == mapping.HOLDING_REGISTER_COUNT
    assert registers[mapping.HR_TEMPERATURE] == 9000
    assert registers[mapping.HR_PRESSURE] == 250
    assert registers[mapping.HR_TANK_LEVEL] == 5000
    assert registers[mapping.HR_PUMP_STATE] == 1


def test_build_coils_addresses_match_layout():
    coils = mapping.build_coils(cooling_active=True, inlet_open=False)
    assert len(coils) == mapping.COIL_COUNT
    assert coils[mapping.COIL_COOLING_ACTIVE] is True
    assert coils[mapping.COIL_INLET_OPEN] is False
