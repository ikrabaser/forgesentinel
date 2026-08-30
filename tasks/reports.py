"""
On-demand Celery task: build a point-in-time security summary report
for one asset.

Deliberately small: the point of this task is to prove the async-task
infrastructure works end-to-end (a FastAPI route hands off
potentially-slow work, returns a task id immediately, a client polls
for the result - see backend/routers/reports.py), not to build a full
reporting feature. A richer report (PDF export, historical trends,
multi-asset rollups) can be layered onto this same task later without
changing how it's invoked from the API.
"""

from __future__ import annotations

from datetime import datetime, timezone

from db.base import get_session
from db.repository import AlertRepository, AssetRepository, TelemetryRepository
from tasks.celery_app import celery_app


@celery_app.task(name="tasks.generate_asset_report")
def generate_asset_report(asset_code: str) -> dict:
    session = get_session()
    try:
        asset = AssetRepository(session).get_by_code(asset_code)
        if asset is None:
            return {"error": f"unknown asset '{asset_code}'"}

        latest = TelemetryRepository(session).latest_for_asset(asset.id)
        alerts = [a for a in AlertRepository(session).list_all(limit=1000) if a.asset_id == asset.id]

        severity_counts: dict[str, int] = {}
        status_counts: dict[str, int] = {}
        for alert in alerts:
            severity_counts[alert.severity] = severity_counts.get(alert.severity, 0) + 1
            status_counts[alert.status] = status_counts.get(alert.status, 0) + 1

        return {
            "asset_code": asset.asset_code,
            "asset_status": asset.status,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "latest_telemetry": None
            if latest is None
            else {
                "timestamp": latest.timestamp.isoformat(),
                "temperature": latest.temperature,
                "pressure": latest.pressure,
                "tank_level_percent": latest.tank_level_percent,
                "pump_state": latest.pump_state,
            },
            "total_alerts": len(alerts),
            "alert_counts_by_severity": severity_counts,
            "alert_counts_by_status": status_counts,
        }
    finally:
        session.close()
