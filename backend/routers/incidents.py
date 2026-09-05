"""
POST /api/incidents/analyze/{alert_id}, GET /api/incidents/tasks/{task_id},
GET /api/incidents?alert_id=..., GET /api/incidents/{incident_id}.

Two different "GET a result" endpoints exist here, deliberately:
    - GET /tasks/{task_id} polls Celery's result backend (Redis) - it
      answers "is the analysis I just requested done yet", and only
      exists for as long as Celery's result TTL keeps it around.
    - GET /{incident_id} and GET ?alert_id=... read from Postgres via
      IncidentAnalysisRepository - the durable system of record. Once
      an analysis has completed, this is how you look it up later,
      long after its Celery task id has expired from Redis - the same
      "Redis is transport/cache, Postgres is truth" split the rest of
      this project already follows for telemetry and alerts.
"""

from __future__ import annotations

from datetime import datetime, timezone

from celery.result import AsyncResult
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.auth import get_current_actor
from backend.dependencies import get_db
from backend.schemas import (
    IncidentAnalysisOut,
    IncidentAnalysisRequestOut,
    IncidentAnalysisTaskStatusOut,
)
from db.repository import AuditLogRepository, IncidentAnalysisRepository
from tasks.celery_app import celery_app
from tasks.incident_analysis import analyze_incident_task

router = APIRouter(prefix="/incidents", tags=["incidents"])


@router.post("/analyze/{alert_id}", response_model=IncidentAnalysisRequestOut, status_code=202)
def request_incident_analysis(
    alert_id: int, db: Session = Depends(get_db), actor: str = Depends(get_current_actor)
) -> IncidentAnalysisRequestOut:
    task = analyze_incident_task.delay(alert_id)
    AuditLogRepository(db).record(
        actor=actor,
        action="INCIDENT_ANALYSIS_REQUESTED",
        resource_type="alert",
        resource_id=str(alert_id),
        timestamp=datetime.now(timezone.utc),
        details={"task_id": task.id},
    )
    db.commit()
    return IncidentAnalysisRequestOut(task_id=task.id, status=task.status)


@router.get("/tasks/{task_id}", response_model=IncidentAnalysisTaskStatusOut)
def get_incident_analysis_task(task_id: str) -> IncidentAnalysisTaskStatusOut:
    result = AsyncResult(task_id, app=celery_app)

    if result.successful():
        return IncidentAnalysisTaskStatusOut(task_id=task_id, status=result.status, result=result.result)
    if result.failed():
        return IncidentAnalysisTaskStatusOut(task_id=task_id, status=result.status, error=str(result.result))
    return IncidentAnalysisTaskStatusOut(task_id=task_id, status=result.status)


@router.get("", response_model=list[IncidentAnalysisOut])
def list_incident_analyses(
    alert_id: int = Query(..., description="List past analyses for this alert"),
    db: Session = Depends(get_db),
) -> list[IncidentAnalysisOut]:
    return IncidentAnalysisRepository(db).list_for_alert(alert_id)


@router.get("/{incident_id}", response_model=IncidentAnalysisOut)
def get_incident_analysis(incident_id: int, db: Session = Depends(get_db)) -> IncidentAnalysisOut:
    analysis = IncidentAnalysisRepository(db).get(incident_id)
    if analysis is None:
        raise HTTPException(status_code=404, detail=f"incident analysis {incident_id} not found")
    return analysis
