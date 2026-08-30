"""
GET /metrics - Prometheus scrape endpoint for the backend process.

These are APPLICATION metrics, not industrial telemetry - see
collector/metrics.py's module docstring for the full distinction.
forgesentinel_active_assets and the alert counters below answer
"what does the system currently look like from an operations
standpoint", the same kind of question a Grafana panel titled
"assets online" or "open critical alerts" would answer for a human
watching a screen, not something the application itself branches on.

Why these are Gauges recomputed on every scrape, not Counters
incremented as things happen: a Counter only ever goes up - it's
right for "how many requests have we ever served", wrong for "how
many assets are online RIGHT NOW" (which can go down). Computing them
fresh from Postgres on each scrape also sidesteps a real correctness
trap: if the backend ever runs as more than one process/worker, an
in-memory counter would only reflect whichever worker happened to
handle the request, while a value read straight from the database is
correct regardless of which worker answers the scrape.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Response
from prometheus_client import CONTENT_TYPE_LATEST, Gauge, generate_latest
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from db.repository import AlertRepository, AssetRepository

router = APIRouter()

ACTIVE_ASSETS = Gauge("forgesentinel_active_assets", "Assets currently reporting status ONLINE.")
ALERTS_TOTAL = Gauge(
    "forgesentinel_alerts_total", "Alerts currently stored, by status.", ["status"]
)
CRITICAL_ALERTS_TOTAL = Gauge(
    "forgesentinel_critical_alerts_total", "Alerts that are OPEN and CRITICAL severity."
)


@router.get("/metrics")
def metrics(db: Session = Depends(get_db)) -> Response:
    ACTIVE_ASSETS.set(AssetRepository(db).count_online())

    alert_repo = AlertRepository(db)
    counts_by_status = alert_repo.count_by_status()
    for status in ("OPEN", "ACKNOWLEDGED", "RESOLVED"):
        ALERTS_TOTAL.labels(status=status).set(counts_by_status.get(status, 0))

    CRITICAL_ALERTS_TOTAL.set(alert_repo.count_open_critical())

    return Response(generate_latest(), media_type=CONTENT_TYPE_LATEST)
