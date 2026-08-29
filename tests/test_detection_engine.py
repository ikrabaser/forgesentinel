from datetime import datetime, timedelta, timezone

from detection.engine import build_default_engine
from collector.telemetry import TelemetryRecord
from simulator.process.pump import PumpState

BASE_TIME = datetime(2026, 1, 1, tzinfo=timezone.utc)


def make_record(**overrides):
    defaults = dict(
        asset_id="PLC-001",
        timestamp=BASE_TIME,
        temperature=50.0,
        pressure=1.0,
        tank_level_percent=50.0,
        pump_state=PumpState.OFF,
        cooling_active=False,
        inlet_open=True,
    )
    defaults.update(overrides)
    return TelemetryRecord(**defaults)


def test_engine_combines_multiple_rules_in_one_pass():
    engine = build_default_engine(expected_poll_interval_seconds=1.0)

    alerts = engine.process_telemetry(
        make_record(temperature=95.0, pressure=5.0, pump_state=PumpState.ON)
    )

    rule_ids = {a.rule_id for a in alerts}
    assert rule_ids == {"RULE-001", "RULE-002"}


def test_engine_returns_empty_list_when_nothing_is_wrong():
    engine = build_default_engine(expected_poll_interval_seconds=1.0)
    alerts = engine.process_telemetry(make_record())
    assert alerts == []


def test_engine_heartbeat_check_uses_telemetry_it_has_seen():
    engine = build_default_engine(expected_poll_interval_seconds=1.0)
    engine.process_telemetry(make_record(timestamp=BASE_TIME))

    alerts_soon = engine.check_heartbeats(["PLC-001"], BASE_TIME + timedelta(seconds=1))
    assert alerts_soon == []

    alerts_later = engine.check_heartbeats(["PLC-001"], BASE_TIME + timedelta(seconds=10))
    assert len(alerts_later) == 1
    assert alerts_later[0].rule_id == "RULE-004"


def test_engine_heartbeat_check_ignores_assets_never_seen():
    engine = build_default_engine(expected_poll_interval_seconds=1.0)
    alerts = engine.check_heartbeats(["NEVER-SEEN"], BASE_TIME)
    assert alerts == []
