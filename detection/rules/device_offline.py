"""
Rule 004 - DEVICE_OFFLINE.

    expected telemetry disappears -> DEVICE_OFFLINE

This rule has a genuinely different SHAPE from Rules 001-003: those
react to a value ARRIVING (evaluate() is only ever called when there's
a fresh TelemetryRecord to look at). DEVICE_OFFLINE has to detect the
opposite - the ABSENCE of an expected arrival - and nothing calls
evaluate() when there's nothing to evaluate. So this class does not
implement TelemetryRule; instead it exposes two separate entry points:

    on_telemetry(record)   - call this whenever a record DOES arrive,
                              to record "this asset was just seen".
    check(asset_id, now)   - call this periodically (independent of
                              whether telemetry arrived), to ask "has
                              too much time passed since we last saw
                              this asset?"

This mirrors how a real monitoring system has to work: staleness
detection needs its own clock-driven check, because if the failure
mode IS "nothing is arriving," you can never rely on an arrival to
trigger the check for you.
"""

from __future__ import annotations

from datetime import datetime, timedelta

from collector.telemetry import TelemetryRecord
from detection.models import Alert, AlertSeverity


class DeviceOfflineRule:
    rule_id = "RULE-004"

    def __init__(self, expected_interval_seconds: float, grace_multiplier: float = 3.0) -> None:
        # grace_multiplier: how many missed polls in a row before we
        # call it offline rather than a single slow/late poll. A
        # grace period avoids raising an alert on ordinary network
        # jitter - exactly the same "debounce noise, not signal"
        # principle as DebouncedTelemetryRule, just clock-driven
        # instead of value-driven.
        self.expected_interval_seconds = expected_interval_seconds
        self.grace_multiplier = grace_multiplier
        self._last_seen: dict[str, datetime] = {}
        self._active: dict[str, bool] = {}

    def on_telemetry(self, record: TelemetryRecord) -> None:
        self._last_seen[record.asset_id] = record.timestamp
        self._active[record.asset_id] = False  # fresh data clears any offline condition

    def check(self, asset_id: str, now: datetime) -> Alert | None:
        last_seen = self._last_seen.get(asset_id)
        if last_seen is None:
            return None  # never seen this asset at all - nothing to compare against

        stale_after = timedelta(seconds=self.expected_interval_seconds * self.grace_multiplier)
        is_stale = (now - last_seen) > stale_after

        was_active = self._active.get(asset_id, False)
        self._active[asset_id] = is_stale

        if is_stale and not was_active:
            return Alert(
                rule_id=self.rule_id,
                asset_id=asset_id,
                severity=AlertSeverity.CRITICAL,
                title="Device offline",
                description=(
                    f"No telemetry received from '{asset_id}' for over "
                    f"{stale_after.total_seconds():.0f}s (last seen at {last_seen.isoformat()})."
                ),
                created_at=now,
            )
        return None
