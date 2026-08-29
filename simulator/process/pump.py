"""
Pump: models the drain pump attached to the tank.

Real-world analogy:
    A physical pump that, when switched ON, pushes liquid out of the
    tank at some flow rate. Pumps can also FAULT (e.g., seized motor,
    tripped breaker) - a state where the pump cannot be trusted to
    actually move liquid even if commanded ON. Modeling FAULT now, even
    though nothing triggers it yet, is what will let later milestones
    simulate "pump commanded ON but tank level keeps rising" as a
    genuine anomaly rather than something we have to bolt on later.
"""

from __future__ import annotations

from enum import Enum


class PumpState(str, Enum):
    ON = "ON"
    OFF = "OFF"
    FAULT = "FAULT"


class Pump:
    def __init__(self, flow_rate: float, state: PumpState = PumpState.OFF) -> None:
        if flow_rate <= 0:
            raise ValueError("flow_rate must be positive")
        self.flow_rate = flow_rate  # liquid moved per tick while ON and healthy
        self.state = state

    def set_state(self, state: PumpState) -> None:
        self.state = state

    def current_outlet_flow(self) -> float:
        """
        How much liquid this pump actually removes this tick.

        FAULT means the pump is commanded/assumed ON but is not
        actually moving liquid - this deliberately mirrors ON's
        "no flow" case so PLC logic can be tested against both.
        """
        if self.state == PumpState.ON:
            return self.flow_rate
        return 0.0
