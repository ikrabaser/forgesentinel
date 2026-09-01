"""
Persists a MODBUS_WRITE audit entry whenever an external Modbus client
sends a genuine write request (FC06/FC16) to this server - see
AuditingSlaveContext in server.py for how those are distinguished from
the simulator's own internal tick updates.

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

logger = logging.getLogger("forgesentinel.modbus_audit")

_FUNCTION_CODE_NAMES = {6: "WRITE_SINGLE_REGISTER", 16: "WRITE_MULTIPLE_REGISTERS"}


def record_modbus_write(asset_id: str, function_code: int, address: int, values: list) -> None:
    session = get_session()
    try:
        AuditLogRepository(session).record(
            actor="modbus-client",
            action="MODBUS_WRITE",
            resource_type="plc",
            resource_id=asset_id,
            timestamp=datetime.now(timezone.utc),
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
