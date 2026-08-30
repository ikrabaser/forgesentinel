"""
tests.check_device_offline is a plain @celery_app.task-decorated
function - calling it directly (not via .delay()/.apply_async())
executes it synchronously in this process, no Redis/worker needed.
That's exactly what these tests do; test_backend_reports_api.py
separately proves the actual .delay()/AsyncResult round-trip.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from db.repository import AlertRepository, AssetRepository
from tasks import heartbeat


def _make_asset(db_session, last_seen: datetime):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=last_seen
    )
    db_session.commit()
    return asset


def test_no_alert_for_recently_seen_asset(monkeypatch, test_engine, db_session):
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(heartbeat, "get_session", sessionmaker(bind=test_engine, future=True))
    _make_asset(db_session, datetime.now(timezone.utc))

    raised = heartbeat.check_device_offline()

    assert raised == 0
    assert AlertRepository(db_session).list_all() == []


def test_alert_raised_for_stale_asset(monkeypatch, test_engine, db_session):
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(heartbeat, "get_session", sessionmaker(bind=test_engine, future=True))
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=100)
    _make_asset(db_session, stale_time)

    raised = heartbeat.check_device_offline()

    assert raised == 1
    alerts = AlertRepository(db_session).list_all()
    assert len(alerts) == 1
    assert alerts[0].rule_id == "RULE-004"
    assert alerts[0].severity == "CRITICAL"
    assert alerts[0].status == "OPEN"


def test_does_not_duplicate_alert_while_already_open(monkeypatch, test_engine, db_session):
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(heartbeat, "get_session", sessionmaker(bind=test_engine, future=True))
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=100)
    _make_asset(db_session, stale_time)

    first_pass = heartbeat.check_device_offline()
    second_pass = heartbeat.check_device_offline()

    assert first_pass == 1
    assert second_pass == 0  # already has an OPEN RULE-004 alert - don't pile on
    assert len(AlertRepository(db_session).list_all()) == 1


def test_rearms_after_open_alert_is_resolved(monkeypatch, test_engine, db_session):
    from sqlalchemy.orm import sessionmaker

    monkeypatch.setattr(heartbeat, "get_session", sessionmaker(bind=test_engine, future=True))
    stale_time = datetime.now(timezone.utc) - timedelta(seconds=100)
    asset = _make_asset(db_session, stale_time)

    heartbeat.check_device_offline()
    alert_repo = AlertRepository(db_session)
    still_stale_alert = alert_repo.list_all()[0]
    alert_repo.resolve(still_stale_alert.id, datetime.now(timezone.utc))
    db_session.commit()

    second_pass = heartbeat.check_device_offline()

    assert second_pass == 1  # asset is still stale and the prior alert is resolved, not open
    assert len(alert_repo.list_all()) == 2
