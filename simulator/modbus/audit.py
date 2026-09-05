"""
Persists a MODBUS_WRITE audit entry - and raises the corresponding
Rule 005 (SUSPICIOUS_CONFIGURATION_CHANGE) alert - whenever an
external Modbus client sends a genuine write request (FC06/FC16) to
this server. See AuditingSlaveContext in server.py for how those are
distinguished from the simulator's own internal tick updates.

Two separate persistence calls (audit log, then alert), each with
their own session/transaction, rather than one combined write: they
are conceptually independent records (an audit trail entry vs. a
detection-engine finding) that happen to share a trigger, the same
"one adapter, two separate downstream effects" shape as
collector/collector.py's _make_detecting_callback feeding both a log
line and detection/persistence's alert sink from one telemetry record.

Runs synchronously and briefly blocks whatever asyncio task calls it.
Acceptable here because a genuine external write is a rare,
exceptional event - our own collector never sends one - not part of
the simulation's per-tick hot path.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone

from db.base import get_session
from db.repository import AuditLogRepository
from detection.persistence import make_persisting_alert_sink
from detection.rules.suspicious_configuration_change import (
    build_suspicious_configuration_change_alert,
)

logger = logging.getLogger("forgesentinel.modbus_audit")

_FUNCTION_CODE_NAMES = {6: "WRITE_SINGLE_REGISTER", 16: "WRITE_MULTIPLE_REGISTERS"}

# One persisting sink shared across every write this process observes,
# consistent with how the collector builds one alert sink for the
# lifetime of its run rather than one per record.
_alert_sink = make_persisting_alert_sink()


def record_modbus_write(asset_id: str, function_code: int, address: int, values: list) -> None:
    timestamp = datetime.now(timezone.utc)

    session = get_session()
    try:
        AuditLogRepository(session).record(
            actor="modbus-client",
            action="MODBUS_WRITE",
            resource_type="plc",
            resource_id=asset_id,
            timestamp=timestamp,
            details={
                "function_code": function_code,
                "function_name": _FUNCTION_CODE_NAMES.get(function_code, str(function_code)),
                "address": address,
                "values": list(values),
            },
        )
        session.commit()
    except Exception:
        session.rollback()
        logger.exception("Failed to persist MODBUS_WRITE audit entry")
    finally:
        session.close()

    alert = build_suspicious_configuration_change_alert(
        asset_id=asset_id,
        function_code=function_code,
        address=address,
        values=values,
        timestamp=timestamp,
    )
    _alert_sink(alert)
