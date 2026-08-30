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

Why this rule uses hysteresis (see detection/rules/base.py) rather
than plain rising-edge debouncing: sharing that exact 90.0C setpoint
with PLCController's cooling logic means temperature naturally
oscillates around 90.0C once cooling kicks in - the process's own
bang-bang control produces repeated crossings of the same single
number, dipping well below 90.0C on every cooling pulse (observed
live: cycling roughly 81C-94C, a ~13C swing, every ~3 seconds) without
ever actually recovering to a normal operating temperature.

clear_margin is therefore deliberately wide (default 20.0C, i.e. an
"all clear" of 70.0C) - comfortably below that oscillation floor and
close to the process's normal, uncooled operating range. The intent:
one ongoing high-temperature excursion produces ONE open alert, not a
fresh one every ~3 seconds for as long as the underlying condition
persists. Once raised, that alert's OPEN -> ACKNOWLEDGED -> RESOLVED
lifecycle (see db/repository.py's AlertRepository) is what tracks
"is this still ongoing", not repeated re-firing of the rule - a small
clear_margin would just move the flooding problem from "every relay
click" to "every relay click below 85C", not solve it.
"""

from __future__ import annotations

from collector.telemetry import TelemetryRecord
from detection.models import Alert, AlertSeverity
from detection.rules.base import DebouncedTelemetryRule


class HighTemperatureRule(DebouncedTelemetryRule):
    rule_id = "RULE-001"

    def __init__(self, threshold: float = 90.0, clear_margin: float = 20.0) -> None:
        super().__init__()
        self.threshold = threshold
        self.clear_threshold = threshold - clear_margin

    def evaluate(self, record: TelemetryRecord) -> Alert | None:
        return self._fire_with_hysteresis(
            record.asset_id,
            record.temperature,
            set_threshold=self.threshold,
            clear_threshold=self.clear_threshold,
            build_alert=lambda: Alert(
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
