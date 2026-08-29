"""
Adapter: converts detection.models.Alert objects into calls against
db/repository.py. Mirrors collector/persistence.py's role exactly -
the one file that knows about both detection/ and db/, so those two
packages don't need to know about each other.
"""

from __future__ import annotations

import logging
from typing import Callable

from db.base import get_session
from db.repository import AssetRepository, AlertRepository
from detection.models import Alert

logger = logging.getLogger("forgesentinel.detection.persistence")

AlertSink = Callable[[Alert], None]


def make_persisting_alert_sink() -> AlertSink:
    """
    Build an AlertSink that persists every Alert to Postgres.

    Alert.asset_id (from detection/) is the business asset_code, e.g.
    "PLC-001" - the same string TelemetryRecord.asset_id carries. We
    resolve it to the numeric Asset row here, the same way
    collector/persistence.py does for telemetry.
    """

    def _sink(alert: Alert) -> None:
        session = get_session()
        try:
            asset_repo = AssetRepository(session)
            alert_repo = AlertRepository(session)

            asset = asset_repo.get_by_code(alert.asset_id)
            if asset is None:
                # Should not normally happen: an asset only ever
                # produces an alert after we've already seen (and
                # therefore upserted) its telemetry at least once. If
                # it does happen, drop the alert rather than crash the
                # collector loop over it - loudly, via a log, not
                # silently.
                logger.warning(
                    "Cannot persist alert for unknown asset '%s' (rule=%s)",
                    alert.asset_id,
                    alert.rule_id,
                )
                return

            alert_repo.create(
                asset_id=asset.id,
                rule_id=alert.rule_id,
                severity=alert.severity.value,
                title=alert.title,
                description=alert.description,
                created_at=alert.created_at,
            )
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to persist alert for %s", alert.asset_id)
            raise
        finally:
            session.close()

    return _sink
