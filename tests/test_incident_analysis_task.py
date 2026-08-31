from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy.orm import sessionmaker

from db.repository import AlertRepository, AssetRepository, IncidentAnalysisRepository, TelemetryRepository
from detection.ai_analyst import IncidentAnalysis
from tasks import incident_analysis


def _make_asset_and_alert(db_session):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()
    alert = AlertRepository(db_session).create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="High temperature",
        description="Temperature 94.3C exceeds the 90.0C safe threshold.",
        created_at=datetime.now(timezone.utc),
    )
    db_session.commit()
    return asset, alert


def test_unknown_alert_returns_error(monkeypatch, test_engine, db_session):
    monkeypatch.setattr(incident_analysis, "get_session", sessionmaker(bind=test_engine, future=True))

    result = incident_analysis.analyze_incident_task(999999)

    assert result == {"error": "unknown alert id 999999"}


def test_analysis_is_persisted_and_returned(monkeypatch, test_engine, db_session):
    monkeypatch.setattr(incident_analysis, "get_session", sessionmaker(bind=test_engine, future=True))

    asset, alert = _make_asset_and_alert(db_session)
    TelemetryRepository(db_session).add(
        asset_id=asset.id,
        timestamp=datetime.now(timezone.utc),
        temperature=94.3,
        pressure=2.5,
        tank_level_percent=40.0,
        pump_state="ON",
        cooling_active=True,
        inlet_open=True,
    )
    db_session.commit()

    fake_result = IncidentAnalysis(
        summary="Temperature climbed steadily after cooling briefly lapsed.",
        possible_causes=["Cooling system intermittent failure", "Sensor drift"],
        recommended_actions=["Verify the physical temperature sensor reading", "Inspect the cooling relay"],
    )

    def _fake_analyze_incident(client, alert_context, asset_context, telemetry_history):
        assert alert_context.rule_id == "RULE-001"
        assert asset_context.asset_code == "PLC-001"
        assert len(telemetry_history) == 1
        return fake_result

    monkeypatch.setattr(incident_analysis, "analyze_incident", _fake_analyze_incident)

    result = incident_analysis.analyze_incident_task(alert.id)

    assert result["alert_id"] == alert.id
    assert result["model"] == incident_analysis.MODEL
    assert result["summary"] == fake_result.summary
    assert result["possible_causes"] == fake_result.possible_causes
    assert result["recommended_actions"] == fake_result.recommended_actions

    persisted = IncidentAnalysisRepository(db_session).list_for_alert(alert.id)
    assert len(persisted) == 1
    assert persisted[0].summary == fake_result.summary


def test_telemetry_outside_lookback_window_is_excluded(monkeypatch, test_engine, db_session):
    monkeypatch.setattr(incident_analysis, "get_session", sessionmaker(bind=test_engine, future=True))

    asset, alert = _make_asset_and_alert(db_session)
    telemetry_repo = TelemetryRepository(db_session)
    # Well before the lookback window - should NOT be included.
    telemetry_repo.add(
        asset_id=asset.id,
        timestamp=alert.created_at - timedelta(hours=2),
        temperature=40.0,
        pressure=1.0,
        tank_level_percent=50.0,
        pump_state="OFF",
        cooling_active=False,
        inlet_open=True,
    )
    # Inside the window - SHOULD be included.
    telemetry_repo.add(
        asset_id=asset.id,
        timestamp=alert.created_at - timedelta(minutes=2),
        temperature=88.0,
        pressure=2.4,
        tank_level_percent=38.0,
        pump_state="ON",
        cooling_active=False,
        inlet_open=True,
    )
    db_session.commit()

    seen_history_lengths = []

    def _fake_analyze_incident(client, alert_context, asset_context, telemetry_history):
        seen_history_lengths.append(len(telemetry_history))
        return IncidentAnalysis(summary="s", possible_causes=[], recommended_actions=[])

    monkeypatch.setattr(incident_analysis, "analyze_incident", _fake_analyze_incident)

    incident_analysis.analyze_incident_task(alert.id)

    assert seen_history_lengths == [1]
