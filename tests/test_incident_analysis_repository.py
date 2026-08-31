from datetime import datetime, timedelta, timezone

from db.repository import (
    AlertRepository,
    AssetRepository,
    IncidentAnalysisRepository,
    TelemetryHistoryRepository,
    TelemetryRepository,
)


def _make_asset(db_session):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()
    return asset


def _make_alert(db_session, asset_id: int):
    alert = AlertRepository(db_session).create(
        asset_id=asset_id,
        rule_id="RULE-001",
        severity="HIGH",
        title="High temperature",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    db_session.flush()
    return alert


def test_create_and_get_incident_analysis(db_session):
    asset = _make_asset(db_session)
    alert = _make_alert(db_session, asset.id)
    repo = IncidentAnalysisRepository(db_session)

    analysis = repo.create(
        alert_id=alert.id,
        model="claude-opus-5",
        summary="Temperature climbed steadily after cooling stopped.",
        possible_causes=["Cooling system failure", "Sensor drift"],
        recommended_actions=["Verify physical sensor reading", "Inspect cooling relay"],
        created_at=datetime.now(timezone.utc),
    )
    db_session.commit()

    fetched = repo.get(analysis.id)
    assert fetched is not None
    assert fetched.alert_id == alert.id
    assert fetched.model == "claude-opus-5"
    assert fetched.possible_causes == ["Cooling system failure", "Sensor drift"]
    assert fetched.recommended_actions == ["Verify physical sensor reading", "Inspect cooling relay"]


def test_get_returns_none_when_missing(db_session):
    assert IncidentAnalysisRepository(db_session).get(999999) is None


def test_list_for_alert_orders_newest_first(db_session):
    asset = _make_asset(db_session)
    alert = _make_alert(db_session, asset.id)
    repo = IncidentAnalysisRepository(db_session)
    base = datetime.now(timezone.utc)

    older = repo.create(
        alert_id=alert.id,
        model="claude-opus-5",
        summary="first pass",
        possible_causes=["a"],
        recommended_actions=["b"],
        created_at=base,
    )
    newer = repo.create(
        alert_id=alert.id,
        model="claude-opus-5",
        summary="re-analysis with more data",
        possible_causes=["c"],
        recommended_actions=["d"],
        created_at=base + timedelta(minutes=5),
    )
    db_session.commit()

    results = repo.list_for_alert(alert.id)
    assert [r.id for r in results] == [newer.id, older.id]


def test_list_for_alert_empty_for_unanalyzed_alert(db_session):
    asset = _make_asset(db_session)
    alert = _make_alert(db_session, asset.id)
    assert IncidentAnalysisRepository(db_session).list_for_alert(alert.id) == []


def test_telemetry_history_since_returns_oldest_first_within_window(db_session):
    asset = _make_asset(db_session)
    telemetry_repo = TelemetryRepository(db_session)
    now = datetime.now(timezone.utc)

    # One sample well before the window, three inside it.
    telemetry_repo.add(
        asset_id=asset.id, timestamp=now - timedelta(minutes=30),
        temperature=50.0, pressure=1.0, tank_level_percent=50.0,
        pump_state="OFF", cooling_active=False, inlet_open=True,
    )
    in_window_1 = telemetry_repo.add(
        asset_id=asset.id, timestamp=now - timedelta(minutes=4),
        temperature=70.0, pressure=1.5, tank_level_percent=55.0,
        pump_state="OFF", cooling_active=False, inlet_open=True,
    )
    in_window_2 = telemetry_repo.add(
        asset_id=asset.id, timestamp=now - timedelta(minutes=2),
        temperature=85.0, pressure=1.8, tank_level_percent=58.0,
        pump_state="ON", cooling_active=False, inlet_open=True,
    )
    in_window_3 = telemetry_repo.add(
        asset_id=asset.id, timestamp=now,
        temperature=94.0, pressure=2.0, tank_level_percent=60.0,
        pump_state="ON", cooling_active=True, inlet_open=True,
    )
    db_session.commit()

    history = TelemetryHistoryRepository(db_session).history_since(
        asset.id, since=now - timedelta(minutes=5)
    )

    assert [row.id for row in history] == [in_window_1.id, in_window_2.id, in_window_3.id]
    assert [row.temperature for row in history] == [70.0, 85.0, 94.0]
