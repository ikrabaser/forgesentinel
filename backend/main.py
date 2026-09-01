"""
FastAPI application entry point.

Run it with:

    uvicorn backend.main:app --reload

The lifespan context manager starts/stops the TelemetryBroadcaster
background task alongside the app itself - it needs to be running for
the whole process lifetime, not scoped to any single request, so it
doesn't belong behind a route or a Depends().
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from backend.broadcaster import TelemetryBroadcaster
from backend.routers import (
    alerts,
    assets,
    audit_log,
    health,
    incidents,
    metrics,
    reports,
    telemetry,
    ws,
)
from backend.websocket_manager import manager

broadcaster = TelemetryBroadcaster(connection_manager=manager, poll_seconds=1.0)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    broadcaster.start()
    yield
    await broadcaster.stop()


app = FastAPI(
    title="ForgeSentinel API",
    description="Defensive OT/ICS security lab - asset inventory, telemetry, and live updates.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health.router)
app.include_router(metrics.router)
app.include_router(assets.router, prefix="/api")
app.include_router(telemetry.router, prefix="/api")
app.include_router(alerts.router, prefix="/api")
app.include_router(reports.router, prefix="/api")
app.include_router(incidents.router, prefix="/api")
app.include_router(audit_log.router, prefix="/api")
app.include_router(ws.router)
