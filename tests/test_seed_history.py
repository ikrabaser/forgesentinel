from datetime import datetime, timezone

import pytest
from sqlalchemy.orm import sessionmaker

from db.repository import AlertRepository, AssetRepository, TelemetryRepository
from scripts.seed_history import seed


def test_seed_produces_plausible_telemetry_and_alert_history(test_engine, monkeypatch, db_session):
    test_session_factory = sessionmaker(bind=test_engine, future=True)
    monkeypatch.setattr("scripts.seed_history.get_session", test_session_factory)

    seed(asset_id="PLC-001", profile="default", hours=2, reset=False)

    asset = AssetRepository(db_session).get_by_code("PLC-001")
    assert asset is not None
    assert asset.asset_type == "PLC"

    telemetry = TelemetryRepository(db_session).list_recent(asset.id, limit=1000)
    assert len(telemetry) > 0
    # 2h at DEFAULT_INTERVAL_MINUTES=5 -> ~24 samples; loosely bound to
    # tolerate the exact off-by-one from the <= now loop boundary.
    assert 20 <= len(telemetry) <= 30
    # Every backfilled row is genuinely in the past, not accidentally
    # stamped "now" for every row.
    now = datetime.now(timezone.utc)
    assert all(row.timestamp <= now for row in telemetry)
    # Rows are actually spread across the window, not all bunched at
    # one end of it (which per-tick engine evaluation writing to the
    # wrong timestamp could produce).
    timestamps = sorted(row.timestamp for row in telemetry)
    assert (timestamps[-1] - timestamps[0]).total_seconds() > 3600

    # Any alerts raised must be real Rule 001-003 alerts, each with a
    # created_at inside the backfilled window - and if not the single
    # most recent one, it should have gone through the same
    # acknowledge->resolve lifecycle a human operator's would.
    alerts = AlertRepository(db_session).list_all(limit=1000)
    for alert in alerts:
        assert alert.rule_id in {"RULE-001", "RULE-002", "RULE-003"}
        assert alert.created_at <= now
    if len(alerts) > 1:
        resolved = [a for a in alerts if a.status == "RESOLVED"]
        assert len(resolved) == len(alerts) - 1
        for alert in resolved:
            assert alert.acknowledged_at is not None
            assert alert.resolved_at is not None
            assert alert.acknowledged_at < alert.resolved_at


def test_seed_reset_clears_previous_history_for_that_asset(test_engine, monkeypatch, db_session):
    test_session_factory = sessionmaker(bind=test_engine, future=True)
    monkeypatch.setattr("scripts.seed_history.get_session", test_session_factory)

    seed(asset_id="PLC-001", profile="default", hours=1, reset=False)
    asset = AssetRepository(db_session).get_by_code("PLC-001")
    first_count = len(TelemetryRepository(db_session).list_recent(asset.id, limit=1000))
    assert first_count > 0

    seed(asset_id="PLC-001", profile="default", hours=1, reset=True)
    second_count = len(TelemetryRepository(db_session).list_recent(asset.id, limit=1000))

    # --reset wipes before re-seeding, so the count reflects ONE run's
    # worth of history, not two runs appended together.
    assert second_count == pytest.approx(first_count, abs=2)


def test_seed_rejects_unknown_profile():
    with pytest.raises(SystemExit):
        seed(asset_id="PLC-001", profile="not-a-real-profile", hours=1, reset=False)
