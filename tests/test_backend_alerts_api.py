from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.dependencies import get_db
from backend.main import app
from db.repository import AlertRepository, AssetRepository


@pytest.fixture()
def client(test_engine, db_session):
    test_session_factory = sessionmaker(bind=test_engine, future=True)

    def _override_get_db():
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _make_asset_and_alert(db_session, status: str | None = None):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()
    alert_repo = AlertRepository(db_session)
    alert = alert_repo.create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="High temperature",
        description="Temperature exceeds threshold",
        created_at=datetime.now(timezone.utc),
    )
    if status == "ACKNOWLEDGED":
        alert_repo.acknowledge(alert.id, datetime.now(timezone.utc))
    elif status == "RESOLVED":
        alert_repo.resolve(alert.id, datetime.now(timezone.utc))
    db_session.commit()
    return alert


def test_list_alerts_empty(client):
    response = client.get("/api/alerts")
    assert response.status_code == 200
    assert response.json() == []


def test_list_and_get_alert(client, db_session):
    alert = _make_asset_and_alert(db_session)

    list_response = client.get("/api/alerts")
    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) == 1
    assert body[0]["rule_id"] == "RULE-001"
    assert body[0]["status"] == "OPEN"

    get_response = client.get(f"/api/alerts/{alert.id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == alert.id


def test_get_alert_404_when_missing(client):
    response = client.get("/api/alerts/999999")
    assert response.status_code == 404


def test_list_alerts_filters_by_status(client, db_session):
    _make_asset_and_alert(db_session, status="RESOLVED")

    open_only = client.get("/api/alerts", params={"status": "OPEN"})
    assert open_only.status_code == 200
    assert open_only.json() == []

    resolved_only = client.get("/api/alerts", params={"status": "RESOLVED"})
    assert resolved_only.status_code == 200
    assert len(resolved_only.json()) == 1


def test_list_alerts_rejects_invalid_status(client):
    response = client.get("/api/alerts", params={"status": "NOT_A_REAL_STATUS"})
    assert response.status_code == 422


def test_acknowledge_alert_transitions_to_acknowledged(client, db_session):
    alert = _make_asset_and_alert(db_session)

    response = client.post(f"/api/alerts/{alert.id}/acknowledge")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ACKNOWLEDGED"
    assert body["acknowledged_at"] is not None


def test_resolve_alert_transitions_to_resolved(client, db_session):
    alert = _make_asset_and_alert(db_session)

    response = client.post(f"/api/alerts/{alert.id}/resolve")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "RESOLVED"
    assert body["resolved_at"] is not None


def test_acknowledge_404_for_missing_alert(client):
    response = client.post("/api/alerts/999999/acknowledge")
    assert response.status_code == 404


def test_resolve_404_for_missing_alert(client):
    response = client.post("/api/alerts/999999/resolve")
    assert response.status_code == 404
