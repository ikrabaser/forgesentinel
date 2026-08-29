"""
Rule 003 - PROCESS_ANOMALY.

    pump == OFF AND tank level continues increasing abnormally
    -> PROCESS_ANOMALY

The tricky part of this rule is "abnormally" - a rising tank level
while the pump is off is completely NORMAL in our simulator whenever
the level is still below the low threshold (the PLC's own control
logic in simulator/plc/plc.py intentionally keeps the pump off there
so the tank can refill, see PLCController.decide()). So "pump off,
level rising" alone is not anomalous; it's the plant working as
designed.

What genuinely indicates a problem is the PLC's own documented control
rule being violated: PLCController turns the pump ON once level rises
above the low threshold. If telemetry shows the pump reporting OFF for
several consecutive samples WHILE the level is rising AND already
above that low threshold, the actuator isn't doing what plant safety
logic says it should - a real mismatch between commanded and actual
behavior (exactly the kind of gap a stuck valve, a wiring fault, or a
tampered actuator would produce in a real plant).

low_threshold_percent is configured here to match PLCController's
default (see the HighTemperatureRule docstring for why detection
thresholds are independent config that happens to mirror engineering
setpoints, not a code dependency).
"""

from __future__ import annotations

from collections import deque

from collector.telemetry import TelemetryRecord
from detection.models import Alert, AlertSeverity
from detection.rules.base import DebouncedTelemetryRule
from simulator.process.pump import PumpState


class ProcessAnomalyRule(DebouncedTelemetryRule):
    rule_id = "RULE-003"

    def __init__(self, low_threshold_percent: float = 10.0, lookback: int = 3) -> None:
        super().__init__()
        self.low_threshold_percent = low_threshold_percent
        self.lookback = lookback
        self._history: dict[str, deque[TelemetryRecord]] = {}

    def evaluate(self, record: TelemetryRecord) -> Alert | None:
        history = self._history.setdefault(record.asset_id, deque(maxlen=self.lookback))
        history.append(record)

        condition = False
        if len(history) == self.lookback:
            all_pump_off = all(r.pump_state == PumpState.OFF for r in history)
            levels = [r.tank_level_percent for r in history]
            strictly_rising = all(b > a for a, b in zip(levels, levels[1:]))
            above_low_threshold = record.tank_level_percent > self.low_threshold_percent
            condition = all_pump_off and strictly_rising and above_low_threshold

        return self._fire_on_rising_edge(
            record.asset_id,
            condition,
            lambda: Alert(
                rule_id=self.rule_id,
                asset_id=record.asset_id,
                severity=AlertSeverity.HIGH,
                title="Process anomaly: pump inactive while tank level rises above safe floor",
                description=(
                    f"Pump has reported OFF for {self.lookback} consecutive readings while "
                    f"tank level rose to {record.tank_level_percent:.1f}%, above the "
                    f"{self.low_threshold_percent:.1f}% low threshold where plant control "
                    "logic should have switched the pump back ON."
                ),
                created_at=record.timestamp,
            ),
        )
