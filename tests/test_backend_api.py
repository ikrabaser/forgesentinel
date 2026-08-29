"""
Integration tests for the FastAPI backend, run through Starlette's
TestClient (no real HTTP socket - it calls the ASGI app in-process,
which is faster and still exercises the real routing/dependency-
injection/serialization stack).

The get_db dependency is overridden to point at the disposable test
database instead of the real DATABASE_URL, using FastAPI's built-in
dependency_overrides mechanism - the same technique a real project
uses for all DB-backed endpoint testing.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.dependencies import get_db
from backend.main import app
from db.repository import AssetRepository, TelemetryRepository


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


def test_health_reports_ok_when_database_reachable(client):
    response = client.get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok", "database": "ok"}


def test_list_assets_empty(client):
    response = client.get("/api/assets")
    assert response.status_code == 200
    assert response.json() == []


def test_list_and_get_asset(client, db_session):
    AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001",
        name="PLC-001",
        asset_type="PLC",
        seen_at=datetime.now(timezone.utc),
    )
    db_session.commit()

    list_response = client.get("/api/assets")
    assert list_response.status_code == 200
    assets = list_response.json()
    assert len(assets) == 1
    assert assets[0]["asset_code"] == "PLC-001"

    get_response = client.get("/api/assets/PLC-001")
    assert get_response.status_code == 200
    assert get_response.json()["asset_code"] == "PLC-001"


def test_get_asset_404_when_unknown(client):
    response = client.get("/api/assets/DOES-NOT-EXIST")
    assert response.status_code == 404


def test_telemetry_requires_asset_code(client):
    response = client.get("/api/telemetry")
    assert response.status_code == 422  # missing required query param


def test_telemetry_404_for_unknown_asset(client):
    response = client.get("/api/telemetry", params={"asset_code": "DOES-NOT-EXIST"})
    assert response.status_code == 404


def test_telemetry_latest_404_when_no_data_yet(client, db_session):
    AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001",
        name="PLC-001",
        asset_type="PLC",
        seen_at=datetime.now(timezone.utc),
    )
    db_session.commit()

    response = client.get("/api/telemetry/latest", params={"asset_code": "PLC-001"})
    assert response.status_code == 404


def test_telemetry_list_and_latest(client, db_session):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001",
        name="PLC-001",
        asset_type="PLC",
        seen_at=datetime.now(timezone.utc),
    )
    db_session.flush()

    # Explicit, clearly increasing timestamps - relying on datetime.now()
    # called in a tight loop is flaky here: Windows' clock resolution can
    # be coarser than the gap between calls, making insertion order and
    # timestamp order silently disagree.
    base_time = datetime.now(timezone.utc)
    telemetry_repo = TelemetryRepository(db_session)
    for i, temp in enumerate((70.0, 80.0, 90.0)):
        telemetry_repo.add(
            asset_id=asset.id,
            timestamp=base_time + timedelta(seconds=i),
            temperature=temp,
            pressure=2.0,
            tank_level_percent=50.0,
            pump_state="ON",
            cooling_active=False,
            inlet_open=True,
        )
    db_session.commit()

    list_response = client.get(
        "/api/telemetry", params={"asset_code": "PLC-001", "limit": 2}
    )
    assert list_response.status_code == 200
    records = list_response.json()
    assert len(records) == 2  # limit respected
    assert records[0]["temperature"] == 90.0  # newest first

    latest_response = client.get("/api/telemetry/latest", params={"asset_code": "PLC-001"})
    assert latest_response.status_code == 200
    assert latest_response.json()["temperature"] == 90.0
