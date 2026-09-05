"""
GET /api/alerts, GET /api/alerts/{id}, POST /api/alerts/{id}/acknowledge,
POST /api/alerts/{id}/resolve.

Why acknowledge/resolve are POST, not PATCH/PUT:
    These aren't generic "update this field" operations - they're
    named actions with specific meaning and side effects (setting a
    status AND a timestamp together, following the state-machine rules
    in db/repository.py). Modeling them as POST to an action-named
    sub-path (`/acknowledge`, `/resolve`) makes that intent explicit in
    the URL itself, rather than asking a client to know it must PATCH
    exactly `{"status": "ACKNOWLEDGED"}` and nothing else.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth import get_current_actor
from backend.dependencies import get_db
from backend.schemas import AlertOut
from db.repository import AlertRepository, AuditLogRepository
from detection.models import AlertStatus

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get("", response_model=list[AlertOut])
def list_alerts(
    status: AlertStatus | None = Query(None, description="Filter by alert status"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[AlertOut]:
    status_value = status.value if status is not None else None
    return AlertRepository(db).list_all(status=status_value, limit=limit)


@router.get("/{alert_id}", response_model=AlertOut)
def get_alert(alert_id: int, db: Session = Depends(get_db)) -> AlertOut:
    alert = AlertRepository(db).get(alert_id)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"alert {alert_id} not found")
    return alert


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int, db: Session = Depends(get_db), actor: str = Depends(get_current_actor)
) -> AlertOut:
    now = datetime.now(timezone.utc)
    alert = AlertRepository(db).acknowledge(alert_id, now)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"alert {alert_id} not found")
    AuditLogRepository(db).record(
        actor=actor,
        action="ALERT_ACKNOWLEDGED",
        resource_type="alert",
        resource_id=str(alert_id),
        timestamp=now,
        details={"resulting_status": alert.status},
    )
    db.commit()
    return alert


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: int, db: Session = Depends(get_db), actor: str = Depends(get_current_actor)
) -> AlertOut:
    now = datetime.now(timezone.utc)
    alert = AlertRepository(db).resolve(alert_id, now)
    if alert is None:
        raise HTTPException(status_code=404, detail=f"alert {alert_id} not found")
    AuditLogRepository(db).record(
        actor=actor,
        action="ALERT_RESOLVED",
        resource_type="alert",
        resource_id=str(alert_id),
        timestamp=now,
        details={"resulting_status": alert.status},
    )
    db.commit()
    return alert
