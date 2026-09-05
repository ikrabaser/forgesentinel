"""
Integration-level proof that get_current_actor is actually wired into
FastAPI's dependency chain for the mutating routes, not just correct
in isolation (tests/test_auth.py covers the function itself). Exercises
the real Depends(get_current_actor) resolution through a live request.
"""

from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

import backend.auth as auth_module
from backend.dependencies import get_db
from backend.main import app
from db.repository import AlertRepository, AssetRepository


@pytest.fixture()
def client(test_engine, db_session, monkeypatch):
    test_session_factory = sessionmaker(bind=test_engine, future=True)

    def _override_get_db():
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(auth_module, "API_KEYS", {"secret123": "alice"})

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


def _make_asset_and_alert(db_session) -> int:
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
    return alert.id


def test_acknowledge_without_key_is_rejected_when_auth_enabled(client, db_session):
    alert_id = _make_asset_and_alert(db_session)

    response = client.post(f"/api/alerts/{alert_id}/acknowledge")

    assert response.status_code == 401


def test_acknowledge_with_wrong_key_is_rejected(client, db_session):
    alert_id = _make_asset_and_alert(db_session)

    response = client.post(
        f"/api/alerts/{alert_id}/acknowledge",
        headers={"Authorization": "Bearer wrong-key"},
    )

    assert response.status_code == 401


def test_acknowledge_with_valid_key_succeeds_and_attributes_actor(client, db_session):
    alert_id = _make_asset_and_alert(db_session)

    response = client.post(
        f"/api/alerts/{alert_id}/acknowledge",
        headers={"Authorization": "Bearer secret123"},
    )

    assert response.status_code == 200
    audit = client.get(
        "/api/audit-log", headers={"Authorization": "Bearer secret123"}
    ).json()
    assert audit[0]["actor"] == "alice"


def test_read_only_endpoints_stay_open_even_with_auth_enabled(client, db_session):
    # GET routes never take get_current_actor at all - no header
    # needed, even with API_KEYS configured.
    _make_asset_and_alert(db_session)
    response = client.get("/api/alerts")
    assert response.status_code == 200
