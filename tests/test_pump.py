import pytest

from simulator.process.pump import Pump, PumpState


def test_pump_rejects_invalid_flow_rate():
    with pytest.raises(ValueError):
        Pump(flow_rate=0)
    with pytest.raises(ValueError):
        Pump(flow_rate=-5)


def test_pump_defaults_to_off():
    pump = Pump(flow_rate=10)
    assert pump.state == PumpState.OFF
    assert pump.current_outlet_flow() == 0.0


def test_pump_on_produces_flow_rate():
    pump = Pump(flow_rate=10)
    pump.set_state(PumpState.ON)
    assert pump.current_outlet_flow() == 10.0


def test_pump_fault_produces_no_flow():
    pump = Pump(flow_rate=10)
    pump.set_state(PumpState.FAULT)
    assert pump.current_outlet_flow() == 0.0


def test_pump_state_transitions():
    pump = Pump(flow_rate=10)
    pump.set_state(PumpState.ON)
    assert pump.state == PumpState.ON
    pump.set_state(PumpState.FAULT)
    assert pump.state == PumpState.FAULT
    pump.set_state(PumpState.OFF)
    assert pump.state == PumpState.OFF
