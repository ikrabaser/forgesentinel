"""
Tank: models a simple industrial storage vessel.

Real-world analogy:
    A water/chemical storage tank in a plant. Liquid flows in through an
    inlet valve/pump and flows out through an outlet (drain pump). The
    PLC watches the level and must keep it inside a safe operating range.

This class is intentionally "dumb": it has no opinions about safety
thresholds. It just tracks level and applies flow physics for one time
step (`tick`). The PLC decides *what* the flows should be; the Tank
decides *what happens physically* given those flows.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Tank:
    capacity: float  # maximum liquid the tank can hold (e.g., liters)
    level: float = 0.0  # current liquid level, 0 <= level <= capacity

    def __post_init__(self) -> None:
        if self.capacity <= 0:
            raise ValueError("capacity must be positive")
        if not (0.0 <= self.level <= self.capacity):
            raise ValueError("level must be between 0 and capacity")

    @property
    def level_percent(self) -> float:
        """Level as a percentage of capacity, e.g. 0.0-100.0."""
        return (self.level / self.capacity) * 100.0

    def tick(self, inlet_flow: float, outlet_flow: float) -> None:
        """
        Advance the tank state by one simulation time step.

        inlet_flow: amount of liquid entering this tick (>= 0)
        outlet_flow: amount of liquid leaving this tick (>= 0)

        The resulting level is clamped to [0, capacity] because a real
        tank cannot go negative or overflow past its physical capacity
        (in reality overflow is itself an incident — later milestones
        may turn "clamped at capacity while inlet is still open" into
        a detection signal).
        """
        if inlet_flow < 0 or outlet_flow < 0:
            raise ValueError("flows must be non-negative")

        new_level = self.level + inlet_flow - outlet_flow
        self.level = max(0.0, min(self.capacity, new_level))

    def is_high(self, high_threshold_percent: float) -> bool:
        return self.level_percent >= high_threshold_percent

    def is_low(self, low_threshold_percent: float) -> bool:
        return self.level_percent <= low_threshold_percent
