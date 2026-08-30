from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from db.repository import AlertRepository, AssetRepository, TelemetryRepository
from tasks import reports


def test_report_for_unknown_asset_returns_error(monkeypatch, test_engine, db_session):
    monkeypatch.setattr(reports, "get_session", sessionmaker(bind=test_engine, future=True))

    result = reports.generate_asset_report("NEVER-SEEN")

    assert result == {"error": "unknown asset 'NEVER-SEEN'"}


def test_report_includes_latest_telemetry_and_alert_counts(monkeypatch, test_engine, db_session):
    monkeypatch.setattr(reports, "get_session", sessionmaker(bind=test_engine, future=True))

    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()
    TelemetryRepository(db_session).add(
        asset_id=asset.id,
        timestamp=datetime.now(timezone.utc),
        temperature=95.0,
        pressure=2.0,
        tank_level_percent=50.0,
        pump_state="ON",
        cooling_active=True,
        inlet_open=True,
    )
    alert_repo = AlertRepository(db_session)
    alert_repo.create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="High temperature",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    resolved = alert_repo.create(
        asset_id=asset.id,
        rule_id="RULE-002",
        severity="CRITICAL",
        title="High pressure",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    alert_repo.resolve(resolved.id, datetime.now(timezone.utc))
    db_session.commit()

    result = reports.generate_asset_report("PLC-001")

    assert result["asset_code"] == "PLC-001"
    assert result["latest_telemetry"]["temperature"] == 95.0
    assert result["total_alerts"] == 2
    assert result["alert_counts_by_severity"] == {"HIGH": 1, "CRITICAL": 1}
    assert result["alert_counts_by_status"] == {"OPEN": 1, "RESOLVED": 1}


def test_report_handles_asset_with_no_telemetry_or_alerts(monkeypatch, test_engine, db_session):
    monkeypatch.setattr(reports, "get_session", sessionmaker(bind=test_engine, future=True))
    AssetRepository(db_session).upsert_seen(
        asset_code="TEMP-001",
        name="TEMP-001",
        asset_type="TEMPERATURE_SENSOR",
        seen_at=datetime.now(timezone.utc),
    )
    db_session.commit()

    result = reports.generate_asset_report("TEMP-001")

    assert result["latest_telemetry"] is None
    assert result["total_alerts"] == 0
    assert result["alert_counts_by_severity"] == {}
