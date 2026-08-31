"""
On-demand Celery task: run the AI Incident Analyst against one alert.

Same reasoning as tasks/reports.py for why this is a Celery task and
not a synchronous FastAPI route call: a Claude request can take
several seconds, and a route handling it synchronously would block the
HTTP response for that whole stretch. See backend/routers/incidents.py
for the hand-off pattern (POST returns a task id immediately, GET
polls for the result).

This is the ONE place that wires detection.ai_analyst (pure prompt
logic) together with the database and the real Anthropic client - the
same "adapter" role collector/persistence.py and
detection/persistence.py already play for their own pieces.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import anthropic

from db.base import get_session
from db.repository import AlertRepository, IncidentAnalysisRepository, TelemetryHistoryRepository
from detection.ai_analyst import (
    MODEL,
    AlertContext,
    AssetContext,
    TelemetrySample,
    analyze_incident,
)
from tasks.celery_app import celery_app

# How far back before the alert was raised to pull telemetry for
# context. 10 minutes comfortably covers a full HIGH_TEMPERATURE-style
# excursion (see detection/rules/high_temperature.py's hysteresis
# timing) without pulling in an unrelated, much older trend.
TELEMETRY_LOOKBACK = timedelta(minutes=10)


@celery_app.task(name="tasks.analyze_incident")
def analyze_incident_task(alert_id: int) -> dict:
    session = get_session()
    try:
        alert = AlertRepository(session).get(alert_id)
        if alert is None:
            return {"error": f"unknown alert id {alert_id}"}

        asset = alert.asset  # ORM relationship - already the right Asset row
        history_rows = TelemetryHistoryRepository(session).history_since(
            asset.id, since=alert.created_at - TELEMETRY_LOOKBACK
        )

        alert_context = AlertContext(
            rule_id=alert.rule_id,
            severity=alert.severity,
            title=alert.title,
            description=alert.description,
            status=alert.status,
            created_at=alert.created_at,
        )
        asset_context = AssetContext(
            asset_code=asset.asset_code, asset_type=asset.asset_type, status=asset.status
        )
        telemetry_samples = [
            TelemetrySample(
                timestamp=row.timestamp,
                temperature=row.temperature,
                pressure=row.pressure,
                tank_level_percent=row.tank_level_percent,
                pump_state=row.pump_state,
                cooling_active=row.cooling_active,
                inlet_open=row.inlet_open,
            )
            for row in history_rows
        ]

        client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from the environment
        analysis = analyze_incident(client, alert_context, asset_context, telemetry_samples)

        record = IncidentAnalysisRepository(session).create(
            alert_id=alert.id,
            model=MODEL,
            summary=analysis.summary,
            possible_causes=analysis.possible_causes,
            recommended_actions=analysis.recommended_actions,
            created_at=datetime.now(timezone.utc),
        )
        session.commit()

        return {
            "id": record.id,
            "alert_id": record.alert_id,
            "model": record.model,
            "summary": record.summary,
            "possible_causes": record.possible_causes,
            "recommended_actions": record.recommended_actions,
            "created_at": record.created_at.isoformat(),
        }
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()
