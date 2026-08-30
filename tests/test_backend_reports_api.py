"""
Exercises the real POST -> task id -> GET round trip through Celery's
API, using `task_always_eager` so it runs with no Redis broker/worker
needed: `.delay()` executes the task inline and `task_store_eager_result`
makes that result retrievable via AsyncResult(task_id) afterwards,
exactly like a real deployment's GET would look it up from Redis.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
import redis
from fastapi.testclient import TestClient
from sqlalchemy.orm import sessionmaker

from backend.dependencies import get_db
from backend.main import app
from db.repository import AssetRepository
from tasks.celery_app import BROKER_URL, celery_app
from tasks import reports as reports_task


@pytest.fixture(autouse=True)
def _require_redis():
    """
    Mirrors conftest.py's test_engine skip-if-unreachable for
    Postgres: these tests need the real Celery result backend
    (task_store_eager_result still writes there, even in eager mode -
    see the module docstring), so skip cleanly rather than failing
    hard when Redis isn't running.
    """
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

    monkeypatch.setattr(reports_task, "get_session", test_session_factory)
    celery_app.conf.task_always_eager = True
    celery_app.conf.task_eager_propagates = True
    celery_app.conf.task_store_eager_result = True

    app.dependency_overrides[get_db] = _override_get_db
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()
        celery_app.conf.task_always_eager = False


def test_request_report_for_known_asset_returns_completed_result(client, db_session):
    AssetRepository(db_session).upsert_seen(
        asset_code="PLC-001", name="PLC-001", asset_type="PLC", seen_at=datetime.now(timezone.utc)
    )
    db_session.commit()

    post_response = client.post("/api/reports/PLC-001")
    assert post_response.status_code == 202
    task_id = post_response.json()["task_id"]

    get_response = client.get(f"/api/reports/{task_id}")
    assert get_response.status_code == 200
    body = get_response.json()
    assert body["status"] == "SUCCESS"
    assert body["result"]["asset_code"] == "PLC-001"


def test_request_report_for_unknown_asset_completes_with_error_payload(client):
    post_response = client.post("/api/reports/NEVER-SEEN")
    task_id = post_response.json()["task_id"]

    get_response = client.get(f"/api/reports/{task_id}")
    body = get_response.json()
    assert body["status"] == "SUCCESS"  # the task ran fine - it just found no such asset
    assert body["result"]["error"] == "unknown asset 'NEVER-SEEN'"


def test_get_report_for_unknown_task_id_is_pending():
    response = TestClient(app).get("/api/reports/not-a-real-task-id")
    assert response.status_code == 200
    assert response.json()["status"] == "PENDING"
