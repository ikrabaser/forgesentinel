"""
FastAPI application entry point.

This file's only job is to build the `app` object and wire routers
into it - it deliberately contains no business logic. Run it with:

    uvicorn backend.main:app --reload
"""

from __future__ import annotations

from fastapi import FastAPI

from backend.routers import alerts, assets, health, telemetry

app = FastAPI(
    title="ForgeSentinel API",
    description="Defensive OT/ICS security lab - asset inventory and telemetry API.",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(assets.router, prefix="/api")
app.include_router(telemetry.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
