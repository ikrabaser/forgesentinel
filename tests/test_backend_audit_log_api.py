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
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    db_session.commit()
    return alert


def test_list_audit_log_empty(client):
    response = client.get("/api/audit-log")
    assert response.status_code == 200
    assert response.json() == []


def test_acknowledge_alert_writes_audit_entry(client, db_session):
    alert = _make_asset_and_alert(db_session)

    response = client.post(f"/api/alerts/{alert.id}/acknowledge")
    assert response.status_code == 200

    audit = client.get("/api/audit-log").json()
    assert len(audit) == 1
    assert audit[0]["action"] == "ALERT_ACKNOWLEDGED"
    assert audit[0]["resource_type"] == "alert"
    assert audit[0]["resource_id"] == str(alert.id)
    assert audit[0]["actor"] == "api-client"
    assert audit[0]["details"] == {"resulting_status": "ACKNOWLEDGED"}


def test_resolve_alert_writes_audit_entry(client, db_session):
    alert = _make_asset_and_alert(db_session)

    response = client.post(f"/api/alerts/{alert.id}/resolve")
    assert response.status_code == 200

    audit = client.get("/api/audit-log", params={"action": "ALERT_RESOLVED"}).json()
    assert len(audit) == 1
    assert audit[0]["resource_id"] == str(alert.id)


def test_failed_acknowledge_writes_no_audit_entry(client):
    response = client.post("/api/alerts/999999/acknowledge")
    assert response.status_code == 404

    assert client.get("/api/audit-log").json() == []


def test_audit_log_filters_by_resource_type(client, db_session):
    alert = _make_asset_and_alert(db_session)
    client.post(f"/api/alerts/{alert.id}/acknowledge")

    matching = client.get("/api/audit-log", params={"resource_type": "alert"}).json()
    assert len(matching) == 1

    none_matching = client.get("/api/audit-log", params={"resource_type": "plc"}).json()
    assert none_matching == []


def test_audit_log_respects_limit(client, db_session):
    alert = _make_asset_and_alert(db_session)
    client.post(f"/api/alerts/{alert.id}/acknowledge")
    client.post(f"/api/alerts/{alert.id}/resolve")

    limited = client.get("/api/audit-log", params={"limit": 1}).json()
    assert len(limited) == 1
