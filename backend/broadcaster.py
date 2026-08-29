"""
TelemetryBroadcaster: a background task, independent of any single
HTTP/WebSocket request, that periodically checks the database for new
telemetry and alerts and pushes them to every connected WebSocket
client via ConnectionManager.

Why polling the database, not a true push from the collector process:
    The collector (Milestone 3) and this backend are separate OS
    processes with no direct connection to each other - the collector
    writes to Postgres and has no idea the backend, or any WebSocket
    client, even exists. A real push architecture between processes
    would need a message broker (Redis pub/sub, etc.) - exactly the
    kind of infrastructure project rule #23 says not to add before
    there's a concrete problem needing it. Milestone 10 (Redis +
    Celery) is where that becomes justified for other reasons; until
    then, this backend polling Postgres on a short interval and then
    genuinely PUSHING each new row out over WebSocket already delivers
    what the dashboard needs - the browser never has to poll.

Why the DB query runs via asyncio.to_thread():
    Our Session/repository layer is synchronous (Milestone 4's
    decision). Calling a blocking DB call directly inside an `async
    def` would block the entire event loop - including every other
    WebSocket connection's traffic - for however long that query
    takes. asyncio.to_thread() runs the blocking call in a worker
    thread instead, so the event loop stays free to service other
    connections while a poll is in flight.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Callable

from sqlalchemy.orm import Session

from backend.websocket_manager import ConnectionManager
from db.base import get_session
from db.models import Alert, Telemetry
from db.repository import AlertRepository, AssetRepository, TelemetryRepository

logger = logging.getLogger("forgesentinel.backend.broadcaster")


def _telemetry_message(asset_code: str, row: Telemetry) -> dict:
    return {
        "type": "telemetry",
        "asset_code": asset_code,
        "id": row.id,
        "timestamp": row.timestamp.isoformat(),
        "temperature": row.temperature,
        "pressure": row.pressure,
        "tank_level_percent": row.tank_level_percent,
        "pump_state": row.pump_state,
        "cooling_active": row.cooling_active,
        "inlet_open": row.inlet_open,
    }


def _alert_message(row: Alert) -> dict:
    return {
        "type": "alert",
        "id": row.id,
        "asset_id": row.asset_id,
        "rule_id": row.rule_id,
        "severity": row.severity,
        "title": row.title,
        "description": row.description,
        "status": row.status,
        "created_at": row.created_at.isoformat(),
    }


class TelemetryBroadcaster:
    def __init__(
        self,
        connection_manager: ConnectionManager,
        session_factory: Callable[[], Session] = get_session,
        poll_seconds: float = 1.0,
    ) -> None:
        self.connection_manager = connection_manager
        self.session_factory = session_factory
        self.poll_seconds = poll_seconds
        self._last_telemetry_id: dict[int, int] = {}
        self._last_alert_id: int = 0
        self._task: asyncio.Task | None = None

    def start(self) -> None:
        self._task = asyncio.create_task(self._run_forever())

    async def stop(self) -> None:
        if self._task is None:
            return
        self._task.cancel()
        try:
            await self._task
        except asyncio.CancelledError:
            pass

    async def _run_forever(self) -> None:
        while True:
            messages = await asyncio.to_thread(self._poll_once)
            for message in messages:
                await self.connection_manager.broadcast(message)
            await asyncio.sleep(self.poll_seconds)

    def _poll_once(self) -> list[dict]:
        """
        Synchronous by design (see module docstring) - runs inside a
        worker thread via asyncio.to_thread, never directly on the
        event loop.
        """
        messages: list[dict] = []
        try:
            session = self.session_factory()
        except Exception:
            logger.exception("Broadcaster could not open a database session")
            return messages

        try:
            asset_repo = AssetRepository(session)
            telemetry_repo = TelemetryRepository(session)
            alert_repo = AlertRepository(session)

            for asset in asset_repo.list_all():
                latest = telemetry_repo.latest_for_asset(asset.id)
                if latest is None:
                    continue
                last_seen_id = self._last_telemetry_id.get(asset.id)
                if last_seen_id is None or latest.id > last_seen_id:
                    self._last_telemetry_id[asset.id] = latest.id
                    messages.append(_telemetry_message(asset.asset_code, latest))

            recent_alerts = alert_repo.list_all(limit=50)
            new_alerts = [a for a in recent_alerts if a.id > self._last_alert_id]
            for alert in reversed(new_alerts):  # oldest-first, matches arrival order
                messages.append(_alert_message(alert))
            if recent_alerts:
                self._last_alert_id = max(self._last_alert_id, recent_alerts[0].id)
        except Exception:
            logger.exception("Broadcaster poll failed")
        finally:
            session.close()

        return messages
