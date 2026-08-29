"""
PLCController: the control-logic brain, deliberately separated from
any physical simulation or I/O.

Real-world analogy:
    A PLC's "ladder logic" / control program: read inputs, apply fixed
    safety rules, decide outputs. In a real PLC this runs many times a
    second against physical wiring. Here it runs once per simulation
    tick against our simulated tank/pump/sensors.

Design choice - why this class has NO reference to Tank/Pump objects:
    Keeping this as pure "readings in -> decisions out" logic (no
    mutation, no I/O) makes it trivial to unit test every rule in
    isolation, and mirrors how real control logic is validated against
    a table of inputs/outputs before it's ever wired to hardware.
"""

from __future__ import annotations

from dataclasses import dataclass

from simulator.process.pump import PumpState


@dataclass
class PLCReadings:
    tank_level_percent: float
    temperature: float
    pressure: float
    pump_state: PumpState


@dataclass
class PLCDecision:
    pump_command: PumpState  # ON or OFF (PLC never commands FAULT)
    cooling_active: bool
    inlet_open: bool


class PLCController:
    def __init__(
        self,
        tank_high_threshold_percent: float = 90.0,
        tank_low_threshold_percent: float = 10.0,
        temp_safe_threshold: float = 90.0,
        pressure_max_safe: float = 4.0,
    ) -> None:
        self.tank_high_threshold_percent = tank_high_threshold_percent
        self.tank_low_threshold_percent = tank_low_threshold_percent
        self.temp_safe_threshold = temp_safe_threshold
        self.pressure_max_safe = pressure_max_safe

    def decide(self, readings: PLCReadings) -> PLCDecision:
        """
        Apply the safety rules from the spec:

            if tank level > high threshold: stop inlet
            if temperature > safe threshold: activate cooling
            if pressure > maximum safe pressure: trigger process alarm
              (Milestone 1 has no alert system yet, so we surface this
              as "force pump ON" - draining the tank is the immediate
              safe response available to us right now.)

        Pump drains the tank, so:
            - keep draining (pump ON) whenever level is above the low
              threshold, to actively manage level.
            - stop draining (pump OFF) once level reaches/below the low
              threshold, so the tank doesn't run empty.
        """
        inlet_open = readings.tank_level_percent < self.tank_high_threshold_percent

        cooling_active = readings.temperature > self.temp_safe_threshold

        overpressure = readings.pressure > self.pressure_max_safe
        if overpressure or readings.tank_level_percent > self.tank_low_threshold_percent:
            pump_command = PumpState.ON
        else:
            pump_command = PumpState.OFF

        return PLCDecision(
            pump_command=pump_command,
            cooling_active=cooling_active,
            inlet_open=inlet_open,
        )
