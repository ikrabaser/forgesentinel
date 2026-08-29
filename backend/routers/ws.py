"""
WS /ws/live - the single WebSocket endpoint clients connect to for
live telemetry + alert updates.

This endpoint has no business logic of its own: it accepts a
connection, registers it with the shared ConnectionManager, and keeps
reading (discarding) anything the client sends purely so it notices a
disconnect promptly. All actual message content comes from
TelemetryBroadcaster calling manager.broadcast() independently - this
route and the broadcaster only share the ConnectionManager instance,
nothing else.
"""

from __future__ import annotations

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.websocket_manager import manager

router = APIRouter()


@router.websocket("/ws/live")
async def live_updates(websocket: WebSocket) -> None:
    await manager.connect(websocket)
    try:
        while True:
            # We don't expect meaningful client messages - this just
            # blocks until the client sends something or disconnects,
            # which is how a WebSocket server notices a closed
            # connection rather than holding a dead socket forever.
            await websocket.receive_text()
    except WebSocketDisconnect:
        manager.disconnect(websocket)
