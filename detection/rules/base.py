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

Why hysteresis (_fire_with_hysteresis) exists too, not just the plain
rising-edge check above:
    Rising-edge alone assumes a value crossing a single threshold is a
    clean, deliberate transition. In practice, a value hovering right
    at that boundary - exactly what happens here, since PLCController
    turns cooling on/off at the same 90C setpoint this rule alarms on
    - crosses back and forth many times in quick succession as the
    process's own bang-bang control reacts. Naive edge-triggering
    reports every single crossing as a fresh event: dozens of
    "HIGH_TEMPERATURE" alerts a minute for what is really one ongoing
    excursion. This is "alarm flooding", a well-documented real-world
    ICS/SCADA problem - operators start ignoring alarms once they
    flood, which is how a genuine incident gets missed. The fix is a
    deadband: once active, a rule only clears when the value drops
    past a SECOND, more lenient threshold, not just back below the one
    that set it off. That gap absorbs the noise around the boundary.
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

    def _fire_with_hysteresis(
        self,
        asset_id: str,
        value: float,
        set_threshold: float,
        clear_threshold: float,
        build_alert: Callable[[], Alert],
    ) -> Alert | None:
        """
        Schmitt-trigger style edge detection: fires the first time
        `value` rises past `set_threshold`, then stays "active" (no
        further alerts) until `value` drops past the lower
        `clear_threshold` - only then can a future rise above
        `set_threshold` fire again. Requires clear_threshold <
        set_threshold; the gap between them is the deadband that
        absorbs noise/oscillation right at the boundary.
        """
        was_active = self._active.get(asset_id, False)
        still_active = value >= clear_threshold if was_active else value > set_threshold
        self._active[asset_id] = still_active

        if still_active and not was_active:
            return build_alert()
        return None
