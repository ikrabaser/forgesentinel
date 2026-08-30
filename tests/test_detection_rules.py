from datetime import datetime, timedelta, timezone

from detection.rules.device_offline import DeviceOfflineRule
from detection.rules.high_pressure import HighPressureRule
from detection.rules.high_temperature import HighTemperatureRule
from detection.rules.process_anomaly import ProcessAnomalyRule
from collector.telemetry import TelemetryRecord
from simulator.process.pump import PumpState

BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_record(
    temperature=50.0,
    pressure=1.0,
    tank_level_percent=50.0,
    pump_state=PumpState.OFF,
    cooling_active=False,
    inlet_open=True,
    asset_id="PLC-001",
    timestamp=None,
):
    return TelemetryRecord(
        asset_id=asset_id,
        timestamp=timestamp or BASE_TIME,
        temperature=temperature,
        pressure=pressure,
        tank_level_percent=tank_level_percent,
        pump_state=pump_state,
        cooling_active=cooling_active,
        inlet_open=inlet_open,
    )


# --- Rule 001: HIGH_TEMPERATURE ---


def test_high_temperature_fires_when_over_threshold():
    rule = HighTemperatureRule(threshold=90.0)
    alert = rule.evaluate(make_record(temperature=95.0))
    assert alert is not None
    assert alert.rule_id == "RULE-001"
    assert alert.asset_id == "PLC-001"


def test_high_temperature_does_not_fire_at_or_below_threshold():
    rule = HighTemperatureRule(threshold=90.0)
    assert rule.evaluate(make_record(temperature=90.0)) is None
    assert rule.evaluate(make_record(temperature=50.0)) is None


def test_high_temperature_debounces_repeated_condition():
    rule = HighTemperatureRule(threshold=90.0)
    first = rule.evaluate(make_record(temperature=95.0))
    second = rule.evaluate(make_record(temperature=96.0))  # still over threshold
    assert first is not None
    assert second is None  # no repeat alert while condition persists


def test_high_temperature_rearms_after_condition_clears():
    rule = HighTemperatureRule(threshold=90.0)
    first = rule.evaluate(make_record(temperature=95.0))
    rule.evaluate(make_record(temperature=50.0))  # condition clears
    third = rule.evaluate(make_record(temperature=95.0))  # recurs
    assert first is not None
    assert third is not None


def test_high_temperature_hysteresis_suppresses_flapping_at_boundary():
    """
    Reproduces the real bug this rule's hysteresis was added to fix:
    PLCController's cooling logic shares the same 90.0C setpoint, so
    the simulated plant naturally oscillates just above/below it. A
    dip to 88C (below the 90C set threshold but above the 85C clear
    threshold) must NOT re-arm the rule - only a genuine drop below
    the clear threshold should.
    """
    rule = HighTemperatureRule(threshold=90.0, clear_margin=5.0)
    readings = [95.0, 88.0, 93.0, 87.0, 94.0]  # oscillates around 90, never clears
    alerts = [rule.evaluate(make_record(temperature=t)) for t in readings]

    assert alerts[0] is not None  # initial rising edge
    assert all(a is None for a in alerts[1:])  # every later crossing suppressed


def test_high_temperature_hysteresis_rearms_after_genuine_clear():
    rule = HighTemperatureRule(threshold=90.0, clear_margin=5.0)
    first = rule.evaluate(make_record(temperature=95.0))
    rule.evaluate(make_record(temperature=88.0))  # dip, but not below clear threshold
    still_suppressed = rule.evaluate(make_record(temperature=93.0))
    rule.evaluate(make_record(temperature=80.0))  # genuinely clears (< 85.0)
    third = rule.evaluate(make_record(temperature=95.0))

    assert first is not None
    assert still_suppressed is None
    assert third is not None


# --- Rule 002: HIGH_PRESSURE ---


def test_high_pressure_fires_when_over_threshold():
    rule = HighPressureRule(threshold=4.0)
    alert = rule.evaluate(make_record(pressure=4.5))
    assert alert is not None
    assert alert.rule_id == "RULE-002"
    assert alert.severity.value == "CRITICAL"


def test_high_pressure_does_not_fire_below_threshold():
    rule = HighPressureRule(threshold=4.0)
    assert rule.evaluate(make_record(pressure=2.0)) is None


def test_high_pressure_hysteresis_suppresses_flapping_at_boundary():
    rule = HighPressureRule(threshold=4.0, clear_margin=0.5)
    readings = [4.5, 3.8, 4.3, 3.7]  # oscillates around 4.0, never clears below 3.5
    alerts = [rule.evaluate(make_record(pressure=p)) for p in readings]

    assert alerts[0] is not None
    assert all(a is None for a in alerts[1:])


# --- Rule 003: PROCESS_ANOMALY ---


def test_process_anomaly_fires_on_pump_off_with_rising_level_above_threshold():
    rule = ProcessAnomalyRule(low_threshold_percent=10.0, lookback=3)
    levels = [12.0, 14.0, 16.0]
    alerts = [
        rule.evaluate(make_record(pump_state=PumpState.OFF, tank_level_percent=level))
        for level in levels
    ]
    assert alerts[0] is None
    assert alerts[1] is None
    assert alerts[2] is not None
    assert alerts[2].rule_id == "RULE-003"


def test_process_anomaly_does_not_fire_below_low_threshold():
    """Pump off + rising level below the low threshold is normal refill behavior."""
    rule = ProcessAnomalyRule(low_threshold_percent=10.0, lookback=3)
    levels = [4.0, 6.0, 8.0]  # rising, but never above 10%
    alerts = [
        rule.evaluate(make_record(pump_state=PumpState.OFF, tank_level_percent=level))
        for level in levels
    ]
    assert all(a is None for a in alerts)


def test_process_anomaly_does_not_fire_when_pump_on():
    rule = ProcessAnomalyRule(low_threshold_percent=10.0, lookback=3)
    levels = [12.0, 14.0, 16.0]
    alerts = [
        rule.evaluate(make_record(pump_state=PumpState.ON, tank_level_percent=level))
        for level in levels
    ]
    assert all(a is None for a in alerts)


def test_process_anomaly_does_not_fire_when_level_not_strictly_rising():
    rule = ProcessAnomalyRule(low_threshold_percent=10.0, lookback=3)
    levels = [16.0, 14.0, 16.0]  # not monotonically increasing
    alerts = [
        rule.evaluate(make_record(pump_state=PumpState.OFF, tank_level_percent=level))
        for level in levels
    ]
    assert all(a is None for a in alerts)


# --- Rule 004: DEVICE_OFFLINE ---


def test_device_offline_does_not_fire_for_unknown_asset():
    rule = DeviceOfflineRule(expected_interval_seconds=1.0, grace_multiplier=3.0)
    assert rule.check("PLC-001", BASE_TIME) is None


def test_device_offline_fires_after_grace_period_elapses():
    rule = DeviceOfflineRule(expected_interval_seconds=1.0, grace_multiplier=3.0)
    rule.on_telemetry(make_record(timestamp=BASE_TIME))

    still_ok = rule.check("PLC-001", BASE_TIME + timedelta(seconds=2))
    assert still_ok is None  # within grace (3 * 1s = 3s)

    now_offline = rule.check("PLC-001", BASE_TIME + timedelta(seconds=5))
    assert now_offline is not None
    assert now_offline.rule_id == "RULE-004"


def test_device_offline_debounces_and_rearms():
    rule = DeviceOfflineRule(expected_interval_seconds=1.0, grace_multiplier=3.0)
    rule.on_telemetry(make_record(timestamp=BASE_TIME))

    first = rule.check("PLC-001", BASE_TIME + timedelta(seconds=5))
    second = rule.check("PLC-001", BASE_TIME + timedelta(seconds=6))
    assert first is not None
    assert second is None  # still offline, but already reported

    # Asset comes back online, then goes stale again -> re-arms.
    rule.on_telemetry(make_record(timestamp=BASE_TIME + timedelta(seconds=6)))
    third = rule.check("PLC-001", BASE_TIME + timedelta(seconds=11))
    assert third is not None
