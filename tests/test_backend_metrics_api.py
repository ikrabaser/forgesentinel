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


def test_metrics_endpoint_returns_prometheus_exposition_format(client):
    response = client.get("/metrics")
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/plain")
    assert "forgesentinel_active_assets" in response.text
    assert "forgesentinel_alerts_total" in response.text
    assert "forgesentinel_critical_alerts_total" in response.text


def test_metrics_reflect_current_database_state(client, db_session):
    asset = AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.flush()

    alert_repo = AlertRepository(db_session)
    open_alert = alert_repo.create(
        asset_id=asset.id,
        rule_id="RULE-002",
        severity="CRITICAL",
        title="High pressure",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    resolved_alert = alert_repo.create(
        asset_id=asset.id,
        rule_id="RULE-001",
        severity="HIGH",
        title="High temperature",
        description="d",
        created_at=datetime.now(timezone.utc),
    )
    alert_repo.resolve(resolved_alert.id, datetime.now(timezone.utc))
    db_session.commit()

    body = client.get("/metrics").text

    assert "forgesentinel_active_assets 1.0" in body
    assert 'forgesentinel_alerts_total{status="OPEN"} 1.0' in body
    assert 'forgesentinel_alerts_total{status="RESOLVED"} 1.0' in body
    assert 'forgesentinel_alerts_total{status="ACKNOWLEDGED"} 0.0' in body
    assert "forgesentinel_critical_alerts_total 1.0" in body
