"""
TelemetryRule / DebouncedTelemetryRule: the shared contract every
telemetry-driven detection rule implements.

Why debouncing matters (and why it lives in a shared base class rather
than being reinvented per rule):
    A condition like "temperature is too high" doesn't just become
    true for one instant - it usually STAYS true for many consecutive
    polls while the process is genuinely overheating. A naive rule
    that returns a new Alert every time `evaluate()` sees the
    condition would flood the system with one alert per poll interval
    - "alert fatigue" is a well-documented real-world SOC problem that
    causes genuine incidents to get lost in noise. Debouncing tracks,
    per asset, whether the condition was already active last time we
    checked, and only reports on the OPEN->true transition (the
    "rising edge"). When the condition later clears, the rule re-arms
    so a future recurrence is reported again as a fresh event.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Callable

from collector.telemetry import TelemetryRecord
from detection.models import Alert


class TelemetryRule(ABC):
    rule_id: str

    @abstractmethod
    def evaluate(self, record: TelemetryRecord) -> Alert | None:
        """Inspect one telemetry record and optionally return a new Alert."""


class DebouncedTelemetryRule(TelemetryRule):
    def __init__(self) -> None:
        self._active: dict[str, bool] = {}

    def _fire_on_rising_edge(
        self, asset_id: str, condition: bool, build_alert: Callable[[], Alert]
    ) -> Alert | None:
        was_active = self._active.get(asset_id, False)
        self._active[asset_id] = condition
        if condition and not was_active:
            return build_alert()
        return None
