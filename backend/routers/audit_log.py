"""
GET /api/audit-log - read-only access to the audit trail.

Deliberately the only endpoint here: there is no POST/PUT/DELETE for
audit entries, because nothing outside AuditLogRepository.record()
(called internally by the routes that actually perform an action)
should ever be able to create or edit one directly. An audit log that
clients can freely write to isn't a trustworthy audit log.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.schemas import AuditLogOut
from db.repository import AuditLogRepository

router = APIRouter(prefix="/audit-log", tags=["audit-log"])


@router.get("", response_model=list[AuditLogOut])
def list_audit_log(
    action: str | None = Query(None, description="Filter by action, e.g. ALERT_ACKNOWLEDGED"),
    resource_type: str | None = Query(None, description="Filter by resource type, e.g. alert"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[AuditLogOut]:
    return AuditLogRepository(db).list_recent(limit=limit, action=action, resource_type=resource_type)
