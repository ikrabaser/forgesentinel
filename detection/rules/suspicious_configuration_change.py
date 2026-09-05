"""
Rule 005 - SUSPICIOUS_CONFIGURATION_CHANGE. Implemented as of
Milestone 15+, which built the exact prerequisite this rule was
blocked on (see the git history of this file for the original,
longer explanation of why it couldn't be built honestly before then).

    unexpected PLC configuration/register modification
    -> SUSPICIOUS_CONFIGURATION_CHANGE

What changed: Milestone 15 added a write-audit path on the Modbus
server (AuditingSlaveContext, simulator/modbus/server.py) that
reliably distinguishes a genuine external write (FC06/FC16) from the
simulator's own internal tick updates (which always use fc=3/1). That
answers the question this rule was previously missing an answer to:
"was this write ours, or someone else's?" Our own collector NEVER
writes to PLC registers - it only reads (see collector/modbus_client.py)
- so by construction, any FC06/FC16 request this server observes came
from something other than our own collector. There is still no
"legitimate external writer" (e.g. an engineering workstation) modeled
in this lab, so today every observed write is unauthorized; if one is
ever added, this rule's logic is exactly where that allow-list would
be checked before raising.

Why this rule has NO debouncing, unlike Rules 001-003:
    Debouncing (see detection/rules/base.py) exists for continuous
    values that can hover near a threshold, producing many rapid
    "crossings" for what's really one ongoing condition. A Modbus
    write is not that - it is a discrete, instantaneous event with a
    clear start and end. Two separate writes are two separate security
    events, each worth its own alert, not "the same excursion still
    ongoing." There is no state to track between calls.
"""

from __future__ import annotations

from datetime import datetime

from detection.models import Alert, AlertSeverity

RULE_ID = "RULE-005"

_FUNCTION_CODE_NAMES = {6: "WRITE_SINGLE_REGISTER", 16: "WRITE_MULTIPLE_REGISTERS"}


def build_suspicious_configuration_change_alert(
    asset_id: str,
    function_code: int,
    address: int,
    values: list,
    timestamp: datetime,
) -> Alert:
    """
    Build the Alert for one observed external Modbus write. Pure
    function - no I/O, no debounce state - so every call produces
    exactly one Alert, matching the "each write is its own event"
    reasoning above.
    """
    function_name = _FUNCTION_CODE_NAMES.get(function_code, str(function_code))
    return Alert(
        rule_id=RULE_ID,
        asset_id=asset_id,
        severity=AlertSeverity.CRITICAL,
        title="Suspicious configuration change",
        description=(
            f"An external Modbus client sent a {function_name} (FC{function_code}) "
            f"request to register address {address} with values={list(values)}. "
            f"This collector never writes to PLC registers, so this write bypassed "
            f"the PLC's own control logic entirely."
        ),
        created_at=timestamp,
    )
