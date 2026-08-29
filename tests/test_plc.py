from simulator.plc.plc import PLCController, PLCReadings
from simulator.process.pump import PumpState


def make_controller():
    return PLCController(
        tank_high_threshold_percent=90.0,
        tank_low_threshold_percent=10.0,
        temp_safe_threshold=90.0,
        pressure_max_safe=4.0,
    )


def test_inlet_closes_when_tank_above_high_threshold():
    plc = make_controller()
    readings = PLCReadings(
        tank_level_percent=95.0, temperature=50.0, pressure=1.0, pump_state=PumpState.OFF
    )
    decision = plc.decide(readings)
    assert decision.inlet_open is False


def test_inlet_open_when_tank_below_high_threshold():
    plc = make_controller()
    readings = PLCReadings(
        tank_level_percent=50.0, temperature=50.0, pressure=1.0, pump_state=PumpState.OFF
    )
    decision = plc.decide(readings)
    assert decision.inlet_open is True


def test_cooling_activates_above_safe_temperature():
    plc = make_controller()
    readings = PLCReadings(
        tank_level_percent=50.0, temperature=95.0, pressure=1.0, pump_state=PumpState.OFF
    )
    decision = plc.decide(readings)
    assert decision.cooling_active is True


def test_cooling_inactive_below_safe_temperature():
    plc = make_controller()
    readings = PLCReadings(
        tank_level_percent=50.0, temperature=50.0, pressure=1.0, pump_state=PumpState.OFF
    )
    decision = plc.decide(readings)
    assert decision.cooling_active is False


def test_pump_forced_on_when_pressure_exceeds_max_safe():
    plc = make_controller()
    readings = PLCReadings(
        tank_level_percent=5.0,  # below low threshold - would normally be OFF
        temperature=50.0,
        pressure=4.5,  # above max safe pressure
        pump_state=PumpState.OFF,
    )
    decision = plc.decide(readings)
    assert decision.pump_command == PumpState.ON


def test_pump_off_when_level_at_or_below_low_threshold_and_pressure_safe():
    plc = make_controller()
    readings = PLCReadings(
        tank_level_percent=10.0, temperature=50.0, pressure=1.0, pump_state=PumpState.ON
    )
    decision = plc.decide(readings)
    assert decision.pump_command == PumpState.OFF


def test_pump_on_when_level_above_low_threshold():
    plc = make_controller()
    readings = PLCReadings(
        tank_level_percent=50.0, temperature=50.0, pressure=1.0, pump_state=PumpState.OFF
    )
    decision = plc.decide(readings)
    assert decision.pump_command == PumpState.ON


def test_boundary_temperature_exactly_at_threshold_does_not_trigger_cooling():
    plc = make_controller()
    readings = PLCReadings(
        tank_level_percent=50.0, temperature=90.0, pressure=1.0, pump_state=PumpState.OFF
    )
    decision = plc.decide(readings)
    assert decision.cooling_active is False  # rule is strictly ">" not ">="
