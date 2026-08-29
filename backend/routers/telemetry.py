"""
GET /api/telemetry, GET /api/telemetry/latest - reading back what the
collector has persisted.

Why asset_code is a required query parameter here (not a path segment
like /api/assets/{asset_code}/telemetry):
    Both shapes are defensible REST; we're following the spec's flat
    /api/telemetry?asset_code=... form. Making it a REQUIRED query
    param (not optional/defaulted) is the important part: with only
    one asset in the lab today it would be tempting to default to
    "PLC-001" and let clients omit it, but that silently breaks the
    moment a second asset is added - better to force callers to be
    explicit now than debug an ambiguous "whose telemetry is this"
    later.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.schemas import TelemetryOut
from db.repository import AssetRepository, TelemetryRepository

router = APIRouter(prefix="/telemetry", tags=["telemetry"])


def _require_asset(db: Session, asset_code: str):
    asset = AssetRepository(db).get_by_code(asset_code)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset '{asset_code}' not found")
    return asset


@router.get("/latest", response_model=TelemetryOut)
def latest_telemetry(
    asset_code: str = Query(..., description="e.g. PLC-001"),
    db: Session = Depends(get_db),
) -> TelemetryOut:
    asset = _require_asset(db, asset_code)
    latest = TelemetryRepository(db).latest_for_asset(asset.id)
    if latest is None:
        raise HTTPException(
            status_code=404, detail=f"no telemetry recorded yet for '{asset_code}'"
        )
    return latest


@router.get("", response_model=list[TelemetryOut])
def list_telemetry(
    asset_code: str = Query(..., description="e.g. PLC-001"),
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
) -> list[TelemetryOut]:
    asset = _require_asset(db, asset_code)
    return TelemetryRepository(db).list_recent(asset.id, limit=limit)
