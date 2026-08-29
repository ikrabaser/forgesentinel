"""
Simulation loop: wires Tank + Pump + Sensors + PLCController together
and advances the whole virtual plant one tick at a time.

This is the "main" for Milestone 1. There is no networking, no
database, no Modbus yet - just a Python process you can run and watch
print industrial-looking telemetry to the console.

Order of operations each tick matters and mirrors a real scan cycle:
    1. PLC reads the CURRENT state (readings from the end of the
       previous tick) and decides outputs (pump/cooling/inlet).
    2. Those decisions are applied to the physical simulation:
       pump state is set, tank level moves according to inlet/outlet
       flow, sensors drift toward their new targets.
    3. We log the resulting state.

This "decide, then apply" ordering matches how a real PLC scan cycle
works: it reads inputs, computes outputs from the state as of that
read, then outputs are asserted - it does not use outputs it is still
in the middle of computing to change the same cycle's inputs.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass

from simulator.plc.plc import PLCController, PLCDecision, PLCReadings
from simulator.process.pump import Pump, PumpState
from simulator.process.sensors import PressureSensor, TemperatureSensor
from simulator.process.tank import Tank

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("forgesentinel.simulator")


@dataclass
class PlantConfig:
    tank_capacity: float = 1000.0
    tank_initial_level: float = 500.0
    pump_flow_rate: float = 40.0
    inlet_flow_rate: float = 25.0
    initial_temperature: float = 40.0
    initial_pressure: float = 1.5


class Plant:
    """Owns one tank + pump + sensor set + PLC = one simulated site."""

    def __init__(self, config: PlantConfig | None = None) -> None:
        self.config = config or PlantConfig()

        self.tank = Tank(
            capacity=self.config.tank_capacity,
            level=self.config.tank_initial_level,
        )
        self.pump = Pump(flow_rate=self.config.pump_flow_rate)
        self.temp_sensor = TemperatureSensor(temperature=self.config.initial_temperature)
        self.pressure_sensor = PressureSensor(pressure=self.config.initial_pressure)
        self.plc = PLCController()

        self.tick_count = 0
        # Last PLC decision, kept around so external readers (e.g. the
        # Modbus server in Milestone 2) can report *why* the pump/tank
        # are in their current state, not just the resulting values.
        self.last_decision: PLCDecision | None = None

    def step(self) -> PLCReadings:
        """Advance the plant by exactly one tick. Returns readings after the tick."""
        # 1. PLC decides based on current (pre-tick) readings.
        current_readings = PLCReadings(
            tank_level_percent=self.tank.level_percent,
            temperature=self.temp_sensor.temperature,
            pressure=self.pressure_sensor.pressure,
            pump_state=self.pump.state,
        )
        decision = self.plc.decide(current_readings)
        self.last_decision = decision

        # 2. Apply decisions to the physical simulation.
        self.pump.set_state(decision.pump_command)
        inlet_flow = self.config.inlet_flow_rate if decision.inlet_open else 0.0
        outlet_flow = self.pump.current_outlet_flow()
        self.tank.tick(inlet_flow=inlet_flow, outlet_flow=outlet_flow)

        self.temp_sensor.tick(cooling_active=decision.cooling_active)
        self.pressure_sensor.tick(
            tank_level_percent=self.tank.level_percent,
            temperature=self.temp_sensor.temperature,
        )

        self.tick_count += 1

        return PLCReadings(
            tank_level_percent=self.tank.level_percent,
            temperature=self.temp_sensor.temperature,
            pressure=self.pressure_sensor.pressure,
            pump_state=self.pump.state,
        )


def run(ticks: int = 30, delay_seconds: float = 0.5) -> None:
    plant = Plant()
    logger.info("ForgeSentinel simulator starting (%d ticks)", ticks)

    for _ in range(ticks):
        readings = plant.step()
        logger.info(
            "tick=%03d level=%5.1f%% temp=%6.2fC pressure=%5.2fbar pump=%s",
            plant.tick_count,
            readings.tank_level_percent,
            readings.temperature,
            readings.pressure,
            readings.pump_state.value,
        )
        if delay_seconds:
            time.sleep(delay_seconds)


if __name__ == "__main__":
    run()
