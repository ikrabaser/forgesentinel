"""
Sensors: TemperatureSensor and PressureSensor.

Real-world analogy:
    Physical sensors report a value to the PLC every scan cycle. Real
    sensors don't teleport to a new value instantly - temperature rises
    or falls gradually toward wherever the process is pushing it (e.g.
    toward an "ambient + heating" ceiling, or down toward "cooled"
    floor). We model that with a simple exponential approach toward a
    target value each tick, which keeps behavior deterministic and
    testable while still looking physically plausible.
"""

from __future__ import annotations


class TemperatureSensor:
    def __init__(
        self,
        temperature: float,
        ambient_temp: float = 25.0,
        heating_ceiling: float = 120.0,
        cooling_floor: float = 20.0,
        step_rate: float = 0.15,
    ) -> None:
        self.temperature = temperature
        self.ambient_temp = ambient_temp
        self.heating_ceiling = heating_ceiling
        self.cooling_floor = cooling_floor
        # fraction of the gap to target closed per tick (0 < rate <= 1)
        self.step_rate = step_rate

    def tick(self, cooling_active: bool) -> None:
        """
        Move temperature one step toward its current target.

        cooling_active=False: process naturally drifts toward the
            heating ceiling (simulates ongoing process heat with no
            cooling to counteract it).
        cooling_active=True: temperature drifts down toward the
            cooling floor.
        """
        target = self.cooling_floor if cooling_active else self.heating_ceiling
        self.temperature += (target - self.temperature) * self.step_rate


class PressureSensor:
    def __init__(
        self,
        pressure: float,
        base_pressure: float = 1.0,
        level_coefficient: float = 0.02,
        temp_coefficient: float = 0.01,
        step_rate: float = 0.3,
    ) -> None:
        self.pressure = pressure
        self.base_pressure = base_pressure
        # how much tank level % and temperature contribute to target pressure
        self.level_coefficient = level_coefficient
        self.temp_coefficient = temp_coefficient
        self.step_rate = step_rate

    def tick(self, tank_level_percent: float, temperature: float) -> None:
        """
        Pressure isn't independent in a real closed vessel - it tracks
        fill level and temperature. We approximate that relationship
        with a simple linear target the reading drifts toward, rather
        than jumping to it instantly.
        """
        target = (
            self.base_pressure
            + self.level_coefficient * tank_level_percent
            + self.temp_coefficient * temperature
        )
        self.pressure += (target - self.pressure) * self.step_rate
