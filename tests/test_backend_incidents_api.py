"""
Exercises POST -> task id -> GET (Celery, task_always_eager - same
technique as test_backend_reports_api.py) AND the separate
Postgres-backed list/get-by-id endpoints. The real Claude call
(detection.ai_analyst.analyze_incident) is monkeypatched everywhere
here - these tests verify OUR wiring (routing, persistence, hand-off),
not Claude's output, and must not require a real API key or network
access to run in CI.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.dependencies import get_db
from backend.main import app
from db.repository import AlertRepository, AssetRepository
from detection.ai_analyst import IncidentAnalysis
from tasks import incident_analysis as incident_analysis_task
from tasks.celery_app import BROKER_URL, celery_app

FAKE_ANALYSIS = IncidentAnalysis(
    summary="Temperature climbed steadily after cooling briefly lapsed.",
    possible_causes=["Cooling system intermittent failure"],
    recommended_actions=["Verify the physical temperature sensor reading"],
)


def _fake_analyze_incident(client, alert_context, asset_context, telemetry_history):
    return FAKE_ANALYSIS


@pytest.fixture(autouse=True)
def _require_redis():
    try:
        redis.from_url(BROKER_URL, socket_connect_timeout=2).ping()
    except redis.exceptions.RedisError as exc:
        pytest.skip(f"Redis not reachable at {BROKER_URL} ({exc}); start it with `docker compose up -d`")


@pytest.fixture()
def client(test_engine, db_session, monkeypatch):
    test_session_factory = sessionmaker(bind=test_engine, future=True)

    def _override_get_db():
        session = test_session_factory()
        try:
            yield session
        finally:
            session.close()

    monkeypatch.setattr(incident_analysis_task, "get_session", test_session_factory)
    monkeypatch.setattr(incident_analysis_task, "analyze_incident", _fake_analyze_incident)
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.task_store_eager_result = True

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        celery_app.conf.task_always_eager = False


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


def test_request_analysis_round_trip(client, db_session):
    alert_id = _make_asset_and_alert(db_session)

    post_response = client.post(f"/api/incidents/analyze/{alert_id}")
    assert post_response.status_code == 202
    task_id = post_response.json()["task_id"]

    get_response = client.get(f"/api/incidents/tasks/{task_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["status"] == "SUCCESS"
    assert body["result"]["summary"] == FAKE_ANALYSIS.summary
    assert body["result"]["possible_causes"] == FAKE_ANALYSIS.possible_causes


def test_request_analysis_writes_audit_entry(client, db_session):
    alert_id = _make_asset_and_alert(db_session)

    response = client.post(f"/api/incidents/analyze/{alert_id}")
    task_id = response.json()["task_id"]

    audit = client.get("/api/audit-log", params={"action": "INCIDENT_ANALYSIS_REQUESTED"}).json()
    assert len(audit) == 1
    assert audit[0]["resource_type"] == "alert"
    assert audit[0]["resource_id"] == str(alert_id)
    assert audit[0]["details"] == {"task_id": task_id}


def test_request_analysis_for_unknown_alert_completes_with_error_payload(client):
    post_response = client.post("/api/incidents/analyze/999999")
    task_id = post_response.json()["task_id"]

    get_response = client.get(f"/api/incidents/tasks/{task_id}")
    body = get_response.json()
    assert body["status"] == "SUCCESS"  # the task ran fine - it just found no such alert
    assert body["result"]["error"] == "unknown alert id 999999"


def test_get_task_status_for_unknown_task_id_is_pending():
    response = TestClient(app).get("/api/incidents/tasks/not-a-real-task-id")
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"


def test_list_and_get_persisted_analysis(client, db_session):
    alert_id = _make_asset_and_alert(db_session)

    client.post(f"/api/incidents/analyze/{alert_id}")

    list_response = client.get("/api/incidents", params={"alert_id": alert_id})
    assert list_response.status_code == 200
    body = list_response.json()
    assert len(body) == 1
    assert body[0]["summary"] == FAKE_ANALYSIS.summary
    assert body[0]["alert_id"] == alert_id

    incident_id = body[0]["id"]
    get_response = client.get(f"/api/incidents/{incident_id}")
    assert get_response.status_code == 200
    assert get_response.json()["id"] == incident_id


def test_list_incidents_empty_for_alert_never_analyzed(client, db_session):
    alert_id = _make_asset_and_alert(db_session)

    response = client.get("/api/incidents", params={"alert_id": alert_id})
    assert response.status_code == 200
    assert response.json() == []


def test_get_incident_404_when_missing(client):
    response = client.get("/api/incidents/999999")
    assert response.status_code == 404
