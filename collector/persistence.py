"""
Adapter: converts collector.telemetry.TelemetryRecord objects into
calls against db/repository.py, and packages that up as a
TelemetryCallback the collector loop can plug straight in.

This is the one file that knows about *both* collector/ and db/ - it
exists specifically so neither of those packages has to know about
the other directly (see the note at the top of db/repository.py).
"""

from __future__ import annotations

import logging
from typing import Callable

from db.base import get_session
from db.repository import AssetRepository, TelemetryRepository
from collector.telemetry import TelemetryRecord

logger = logging.getLogger("forgesentinel.collector.persistence")

# Generic defaults for asset upserts. In a real system this metadata
# would come from an engineering/commissioning record, not be
# hard-coded - fine for our lab, but a genuine asset-inventory
# milestone would read this from configuration per asset.
#
# ASSET_NAME used to be the literal string "PLC-001" - harmless while
# there was exactly one asset in the whole system, but a real bug the
# moment a second collector instance runs for a different asset_id:
# every asset upserted through this function would display the name
# "PLC-001" regardless of which one it actually was. Milestone 16
# (multi-asset) surfaced this immediately. Defaulting the name to the
# asset's own code is the honest fallback until per-asset display
# names exist.
ASSET_TYPE = "PLC"
ASSET_PROTOCOL = "Modbus TCP"


def make_persisting_callback(asset_ip: str) -> Callable[[TelemetryRecord], None]:
    """
    Build a TelemetryCallback that persists every record to Postgres:
    upserts the asset's last_seen/status, then inserts a Telemetry row
    in the same transaction, so an asset is never marked "seen" without
    a corresponding telemetry row to back that up.
    """

    def _callback(record: TelemetryRecord) -> None:
        session = get_session()
        try:
            asset_repo = AssetRepository(session)
            telemetry_repo = TelemetryRepository(session)

            asset = asset_repo.upsert_seen(
                asset_code=record.asset_id,
                name=record.asset_id,
                asset_type=ASSET_TYPE,
                seen_at=record.timestamp,
                protocol=ASSET_PROTOCOL,
                ip_address=asset_ip,
            )

            telemetry_repo.add(
                asset_id=asset.id,
                timestamp=record.timestamp,
                temperature=record.temperature,
                pressure=record.pressure,
                tank_level_percent=record.tank_level_percent,
                pump_state=record.pump_state.value,
                cooling_active=record.cooling_active,
                inlet_open=record.inlet_open,
            )

            session.commit()
        except Exception:
            session.rollback()
            logger.exception("Failed to persist telemetry for %s", record.asset_id)
            raise
        finally:
            session.close()

    return _callback
