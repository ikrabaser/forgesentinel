"""
POST /api/reports/{asset_code}, GET /api/reports/{task_id}.

The hand-off pattern this demonstrates:
    POST doesn't run the report - it calls generate_asset_report.delay(),
    which publishes a message to Redis and returns immediately with a
    task id, before any report has actually been built. The route
    responds 202 Accepted (work was accepted, not yet done) rather
    than 200/201. GET then asks Celery's result backend (also Redis)
    for that task id's current state - the same task id works whether
    the task hasn't started yet, is running, or finished seconds or
    hours ago.
"""

from __future__ import annotations

from celery.result import AsyncResult
from fastapi import APIRouter

from backend.schemas import ReportRequestOut, ReportStatusOut
from tasks.celery_app import celery_app
from tasks.reports import generate_asset_report

router = APIRouter(prefix="/reports", tags=["reports"])


@router.post("/{asset_code}", response_model=ReportRequestOut, status_code=202)
def request_report(asset_code: str) -> ReportRequestOut:
    task = generate_asset_report.delay(asset_code)
    return ReportRequestOut(task_id=task.id, status=task.status)


@router.get("/{task_id}", response_model=ReportStatusOut)
def get_report(task_id: str) -> ReportStatusOut:
    result = AsyncResult(task_id, app=celery_app)

    if result.successful():
        return ReportStatusOut(task_id=task_id, status=result.status, result=result.result)
    if result.failed():
        return ReportStatusOut(task_id=task_id, status=result.status, error=str(result.result))
    return ReportStatusOut(task_id=task_id, status=result.status)
