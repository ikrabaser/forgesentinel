"""
Rule 002 - HIGH_PRESSURE.

    pressure > safe limit -> HIGH_PRESSURE

Severity is CRITICAL, one level above HighTemperatureRule's HIGH - a
deliberate judgment call, not an arbitrary choice: overpressure risks
a vessel rupture, a much more immediately dangerous physical failure
mode than a high-but-still-contained temperature. Severity assignment
in a real detection engine encodes a consequence assessment, not just
"how far past the number we are."
"""

from __future__ import annotations

from collector.telemetry import TelemetryRecord
from detection.models import Alert, AlertSeverity
from detection.rules.base import DebouncedTelemetryRule


class HighPressureRule(DebouncedTelemetryRule):
    rule_id = "RULE-002"

    def __init__(self, threshold: float = 4.0) -> None:
        super().__init__()
        self.threshold = threshold

    def evaluate(self, record: TelemetryRecord) -> Alert | None:
        condition = record.pressure > self.threshold

        return self._fire_on_rising_edge(
            record.asset_id,
            condition,
            lambda: Alert(
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
