"""
Rule 001 - HIGH_TEMPERATURE.

    temperature > threshold -> HIGH_TEMPERATURE

The threshold defaults to the same 90.0C used by PLCController's own
cooling-activation setpoint (simulator/plc/plc.py) - not because this
rule imports the PLC (it doesn't; it's fully decoupled), but because a
real detection engine's thresholds are documented plant safety
setpoints, and it's realistic for the security team's threshold to
match engineering's. They're independent configuration values that
happen to agree, not a shared dependency.
"""

from __future__ import annotations

from collector.telemetry import TelemetryRecord
from detection.models import Alert, AlertSeverity
from detection.rules.base import DebouncedTelemetryRule


class HighTemperatureRule(DebouncedTelemetryRule):
    rule_id = "RULE-001"

    def __init__(self, threshold: float = 90.0) -> None:
        super().__init__()
        self.threshold = threshold

    def evaluate(self, record: TelemetryRecord) -> Alert | None:
        condition = record.temperature > self.threshold

        return self._fire_on_rising_edge(
            record.asset_id,
            condition,
            lambda: Alert(
                rule_id=self.rule_id,
                asset_id=record.asset_id,
                severity=AlertSeverity.HIGH,
                title="High temperature",
                description=(
                    f"Temperature {record.temperature:.1f}C exceeds the "
                    f"{self.threshold:.1f}C safe threshold."
                ),
                created_at=record.timestamp,
            ),
        )
