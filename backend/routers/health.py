"""
GET /health - liveness/readiness check.

Why this checks the database, not just "is the process running":
    A process can be alive while completely unable to do its job (DB
    connection pool exhausted, Postgres down). A health check that
    only confirms "the web server answers HTTP" would report healthy
    right up until every other endpoint starts failing. Actually
    running a trivial query (SELECT 1) proves the full path - web
    server -> DB driver -> network -> Postgres - is working.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.schemas import HealthOut

router = APIRouter()


@router.get("/health", response_model=HealthOut)
def health(db: Session = Depends(get_db)) -> HealthOut:
    try:
        db.execute(text("SELECT 1"))
        database_status = "ok"
    except Exception:
        database_status = "unreachable"

    return HealthOut(
        status="ok" if database_status == "ok" else "degraded",
        database=database_status,
    )
