"""
DetectionEngine: runs a set of rules against telemetry and produces
Alerts. This is the single object the collector (or, later, a FastAPI
route) needs to know about - it doesn't need to know that Rules 001
and 003 work differently internally, or that Rule 004 runs on a
different rhythm than the others.
"""

from __future__ import annotations

from datetime import datetime

from collector.telemetry import TelemetryRecord
from detection.models import Alert
from detection.rules.base import TelemetryRule
from detection.rules.device_offline import DeviceOfflineRule
from detection.rules.high_pressure import HighPressureRule
from detection.rules.high_temperature import HighTemperatureRule
from detection.rules.process_anomaly import ProcessAnomalyRule


class DetectionEngine:
    def __init__(
        self,
        telemetry_rules: list[TelemetryRule],
        heartbeat_rule: DeviceOfflineRule | None = None,
    ) -> None:
        self.telemetry_rules = telemetry_rules
        self.heartbeat_rule = heartbeat_rule

    def process_telemetry(self, record: TelemetryRecord) -> list[Alert]:
        """
        Run every telemetry-driven rule against one new record, and
        tell the heartbeat rule (if configured) that this asset was
        just seen. Returns every Alert raised this call (usually
        empty - debouncing means most polls raise nothing at all).
        """
        alerts: list[Alert] = []
        for rule in self.telemetry_rules:
            alert = rule.evaluate(record)
            if alert is not None:
                alerts.append(alert)

        if self.heartbeat_rule is not None:
            self.heartbeat_rule.on_telemetry(record)

        return alerts

    def check_heartbeats(self, asset_ids: list[str], now: datetime) -> list[Alert]:
        """
        Run the offline check for each known asset. Call this on a
        timer independent of telemetry arrival - see the module
        docstring in detection/rules/device_offline.py for why.
        """
        if self.heartbeat_rule is None:
            return []

        alerts: list[Alert] = []
        for asset_id in asset_ids:
            alert = self.heartbeat_rule.check(asset_id, now)
            if alert is not None:
                alerts.append(alert)
        return alerts


def build_default_engine(expected_poll_interval_seconds: float = 1.0) -> DetectionEngine:
    """
    The engine configuration ForgeSentinel actually runs with:
    Rules 001-003 (Rule 004 as the heartbeat rule; Rule 005
    intentionally excluded - see
    detection/rules/suspicious_configuration_change.py).
    """
    return DetectionEngine(
        telemetry_rules=[
            HighTemperatureRule(),
            HighPressureRule(),
            ProcessAnomalyRule(),
        ],
        heartbeat_rule=DeviceOfflineRule(expected_interval_seconds=expected_poll_interval_seconds),
    )
