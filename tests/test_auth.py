import pytest
from fastapi import HTTPException

from backend.auth import _parse_api_keys, get_current_actor


def test_parse_api_keys_basic():
    assert _parse_api_keys("alice:key1,bob:key2") == {"key1": "alice", "key2": "bob"}


def test_parse_api_keys_empty_string():
    assert _parse_api_keys("") == {}


def test_parse_api_keys_skips_malformed_entries():
    # no colon, empty name, empty key - all silently skipped, not raised
    assert _parse_api_keys("garbage,:key,name:,alice:key1") == {"key1": "alice"}


def test_parse_api_keys_trims_whitespace():
    assert _parse_api_keys(" alice : key1 , bob:key2 ") == {"key1": "alice", "key2": "bob"}


@pytest.mark.asyncio
async def test_get_current_actor_returns_placeholder_when_auth_disabled(monkeypatch):
    monkeypatch.setattr("backend.auth.API_KEYS", {})
    actor = await get_current_actor(authorization=None)
    assert actor == "api-client"


@pytest.mark.asyncio
async def test_get_current_actor_ignores_header_when_auth_disabled(monkeypatch):
    # Even a garbage header shouldn't matter - auth is fully off.
    monkeypatch.setattr("backend.auth.API_KEYS", {})
    actor = await get_current_actor(authorization="not a real header")
    assert actor == "api-client"


@pytest.mark.asyncio
async def test_get_current_actor_valid_key_when_auth_enabled(monkeypatch):
    monkeypatch.setattr("backend.auth.API_KEYS", {"secret123": "alice"})
    actor = await get_current_actor(authorization="Bearer secret123")
    assert actor == "alice"


@pytest.mark.asyncio
async def test_get_current_actor_missing_header_when_auth_enabled(monkeypatch):
    monkeypatch.setattr("backend.auth.API_KEYS", {"secret123": "alice"})
    with pytest.raises(HTTPException) as exc_info:
        await get_current_actor(authorization=None)
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_actor_malformed_header_when_auth_enabled(monkeypatch):
    monkeypatch.setattr("backend.auth.API_KEYS", {"secret123": "alice"})
    with pytest.raises(HTTPException) as exc_info:
        await get_current_actor(authorization="secret123")  # missing "Bearer " prefix
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_get_current_actor_invalid_key_when_auth_enabled(monkeypatch):
    monkeypatch.setattr("backend.auth.API_KEYS", {"secret123": "alice"})
    with pytest.raises(HTTPException) as exc_info:
        await get_current_actor(authorization="Bearer wrong-key")
    assert exc_info.value.status_code == 401
