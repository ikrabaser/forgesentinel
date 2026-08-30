"""
Tests for the /ws/live endpoint and ConnectionManager, using
Starlette's real WebSocket test client (an in-process, real ASGI
WebSocket handshake - not a mock).

These tests do NOT go through TelemetryBroadcaster or touch the
database at all: they call manager.broadcast() directly to prove the
WebSocket plumbing (connect, receive, disconnect) works, independent
of whether the broadcaster's DB-polling logic (tested separately in
test_broadcaster.py) is correct.
"""

from __future__ import annotations

import asyncio
import time

from fastapi.testclient import TestClient

from backend.main import app
from backend.websocket_manager import manager


def test_single_client_receives_broadcast_message():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as websocket:
            asyncio.run(manager.broadcast({"type": "telemetry", "temperature": 88.0}))
            message = websocket.receive_json()
            assert message == {"type": "telemetry", "temperature": 88.0}


def test_multiple_clients_all_receive_the_same_broadcast():
    with TestClient(app) as client:
        with client.websocket_connect("/ws/live") as ws_a, client.websocket_connect(
            "/ws/live"
        ) as ws_b:
            asyncio.run(manager.broadcast({"type": "alert", "rule_id": "RULE-001"}))
            assert ws_a.receive_json() == {"type": "alert", "rule_id": "RULE-001"}
            assert ws_b.receive_json() == {"type": "alert", "rule_id": "RULE-001"}


def test_disconnect_removes_client_from_manager():
    """
    The server notices a disconnect (and calls manager.disconnect())
    on its own asyncio task, separate from the thread the TestClient's
    `with` block exits on - there's no guarantee that has already run
    by the time `__exit__` returns here. Polling briefly for the count
    to settle avoids a flaky assertion on that race, without weakening
    what the test actually proves (it still fails if the count never
    drops).
    """

    def _wait_until(predicate, timeout=2.0, interval=0.02):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
            if predicate():
                return True
            time.sleep(interval)
        return predicate()

    with TestClient(app) as client:
        before = manager.connection_count
        with client.websocket_connect("/ws/live"):
            during = manager.connection_count

        assert during == before + 1
        assert _wait_until(lambda: manager.connection_count == before)
