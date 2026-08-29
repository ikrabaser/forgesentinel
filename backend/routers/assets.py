"""
GET /api/assets, GET /api/assets/{asset_code} - the OT asset inventory.

Why the path parameter is asset_code ("PLC-001"), not the numeric
surrogate primary key:
    asset.id is a storage-layer detail - an implementation choice of
    how Postgres happens to index rows. asset_code is the actual
    business identifier: it's what a real engineer would type into an
    HMI, what shows up on a nameplate on the equipment, and what stays
    stable even if the database were rebuilt from scratch. APIs should
    expose identifiers that mean something to the humans using them.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from backend.dependencies import get_db
from backend.schemas import AssetOut
from db.repository import AssetRepository

router = APIRouter(prefix="/assets", tags=["assets"])


@router.get("", response_model=list[AssetOut])
def list_assets(db: Session = Depends(get_db)) -> list[AssetOut]:
    return AssetRepository(db).list_all()


@router.get("/{asset_code}", response_model=AssetOut)
def get_asset(asset_code: str, db: Session = Depends(get_db)) -> AssetOut:
    asset = AssetRepository(db).get_by_code(asset_code)
    if asset is None:
        raise HTTPException(status_code=404, detail=f"asset '{asset_code}' not found")
    return asset
