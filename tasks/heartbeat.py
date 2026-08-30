"""
Celery Beat periodic task: DEVICE_OFFLINE detection (Rule 004).

Why this task exists instead of just calling
DetectionEngine.check_heartbeats() (which already wraps
DeviceOfflineRule) on a timer inside the collector:
    DeviceOfflineRule tracks last-seen timestamps in an in-memory
    dict, fed by on_telemetry() calls from the same process's
    collector loop. That works fine for noticing an asset that's gone
    quiet WHILE the collector is alive - but it can't notice the
    collector itself dying, because the timer that would run the check
    dies with it. This task is deliberately independent: a separate
    Celery worker process, scheduled by Celery Beat, reading
    Asset.last_seen from Postgres - the same column
    AssetRepository.upsert_seen() updates on every successful
    collector poll (Milestone 4). It keeps working regardless of
    whether the collector process is still running.

Debounce is done via AlertRepository.has_open_alert() rather than
DeviceOfflineRule's in-memory _active flag, for the same
process-durability reason: a Celery worker can restart at any time,
and "have we already reported this" needs to survive that.
"""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from db.base import get_session
from db.repository import AlertRepository, AssetRepository
from detection.models import AlertSeverity
from tasks.celery_app import celery_app

logger = logging.getLogger("forgesentinel.tasks.heartbeat")

RULE_ID = "RULE-004"
EXPECTED_INTERVAL_SECONDS = 1.0  # matches the collector's poll interval
GRACE_MULTIPLIER = 5.0


@celery_app.task(name="tasks.check_device_offline")
def check_device_offline() -> int:
    """
    Compare every known asset's last_seen against now; raise a
    RULE-004 alert for any asset stale beyond the grace period that
    doesn't already have one OPEN. Returns the number of alerts
    raised (0 most of the time - that's the expected, healthy case).
    """
    session = get_session()
    raised = 0
    try:
        asset_repo = AssetRepository(session)
        alert_repo = AlertRepository(session)
        now = datetime.now(timezone.utc)
        stale_after = timedelta(seconds=EXPECTED_INTERVAL_SECONDS * GRACE_MULTIPLIER)

        for asset in asset_repo.list_all():
            last_seen = asset.last_seen
            if last_seen.tzinfo is None:
                last_seen = last_seen.replace(tzinfo=timezone.utc)

            if now - last_seen <= stale_after:
                continue
            if alert_repo.has_open_alert(asset.id, RULE_ID):
                continue

            alert_repo.create(
                asset_id=asset.id,
                rule_id=RULE_ID,
                severity=AlertSeverity.CRITICAL.value,
                title="Device offline",
                description=(
                    f"No telemetry received from '{asset.asset_code}' for over "
                    f"{stale_after.total_seconds():.0f}s "
                    f"(last seen at {last_seen.isoformat()})."
                ),
                created_at=now,
            )
            raised += 1

        session.commit()
        return raised
    except Exception:
        session.rollback()
        logger.exception("check_device_offline failed")
        raise
    finally:
        session.close()
