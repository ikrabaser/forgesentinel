"""
Rule 002 - HIGH_PRESSURE.

    pressure > safe limit -> HIGH_PRESSURE

Severity is CRITICAL, one level above HighTemperatureRule's HIGH - a
deliberate judgment call, not an arbitrary choice: overpressure risks
a vessel rupture, a much more immediately dangerous physical failure
mode than a high-but-still-contained temperature. Severity assignment
in a real detection engine encodes a consequence assessment, not just
"how far past the number we are."

Uses the same hysteresis pattern as HighTemperatureRule (see
detection/rules/base.py and its docstring for why the margin needs to
be wide, not just "past the noise floor") for the same reason:
pressure tracks tank level and temperature (simulator/process/
sensors.py), so it can swing close to this threshold too. clear_margin
(default 1.5 bar) keeps one sustained overpressure episode as ONE open
alert rather than one per fluctuation, consistent with
HighTemperatureRule.
"""

from __future__ import annotations

from collector.telemetry import TelemetryRecord
from detection.models import Alert, AlertSeverity
from detection.rules.base import DebouncedTelemetryRule


class HighPressureRule(DebouncedTelemetryRule):
    rule_id = "RULE-002"

    def __init__(self, threshold: float = 4.0, clear_margin: float = 1.5) -> None:
        super().__init__()
        self.threshold = threshold
        self.clear_threshold = threshold - clear_margin

    def evaluate(self, record: TelemetryRecord) -> Alert | None:
        return self._fire_with_hysteresis(
            record.asset_id,
            record.pressure,
            set_threshold=self.threshold,
            clear_threshold=self.clear_threshold,
            build_alert=lambda: Alert(
                rule_id=self.rule_id,
                asset_id=record.asset_id,
                severity=AlertSeverity.CRITICAL,
                title="High pressure",
                description=(
                    f"Pressure {record.pressure:.2f}bar exceeds the "
                    f"{self.threshold:.2f}bar maximum safe pressure."
                ),
                created_at=record.timestamp,
            ),
        )
