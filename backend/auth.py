"""
Minimal API-key authentication, used only by the mutating endpoints
that write an AuditLog entry (POST /api/alerts/{id}/acknowledge,
/resolve, POST /api/incidents/analyze/{id}) - never by read-only GETs,
which stay open. This directly fixes the "actor='api-client'" honest
placeholder those routes (and db/models.py's AuditLog docstring) have
carried since Milestone 15: once configured, AuditLog.actor becomes a
real, distinct principal per caller instead of one shared string.

Deliberately opt-in, not mandatory: if API_KEYS is unset (the
Milestone 15-and-earlier default - see .env.example), every caller is
still attributed to "api-client" and no Authorization header is
required at all, so this doesn't break the "just works out of the
box" experience the rest of this lab has always had. Turning it on is
one env var. This is a trade-off appropriate for a local educational
lab - a real deployment would make auth mandatory, hash the keys at
rest rather than compare plain strings from an env var, and rotate
them - explicitly not what this milestone claims to be.
"""

from __future__ import annotations

import os
from typing import Optional

from fastapi import Header, HTTPException, status


def _parse_api_keys(raw: str) -> dict[str, str]:
    """
    Parse "name1:key1,name2:key2" into {key: name} - keyed by the
    secret itself so lookup at request time is O(1), not a scan.
    Malformed entries (no ":", empty name, or empty key) are skipped
    rather than raising - a typo in this env var should degrade to
    "that key doesn't work", not crash the whole API on startup.
    """
    keys: dict[str, str] = {}
    for pair in raw.split(","):
        pair = pair.strip()
        if not pair:
            continue
        name, sep, key = pair.partition(":")
        name, key = name.strip(), key.strip()
        if sep and name and key:
            keys[key] = name
    return keys


API_KEYS = _parse_api_keys(os.environ.get("API_KEYS", ""))


async def get_current_actor(authorization: Optional[str] = Header(None)) -> str:
    """
    FastAPI dependency: resolves the calling actor for audit-log
    attribution. See the module docstring for the "auth is off unless
    API_KEYS is set" trade-off.
    """
    if not API_KEYS:
        return "api-client"

    if authorization is None or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="missing or malformed Authorization header (expected: Bearer <api-key>)",
        )

    token = authorization.removeprefix("Bearer ").strip()
    actor = API_KEYS.get(token)
    if actor is None:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="invalid API key")

    return actor
