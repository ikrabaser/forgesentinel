"""
ConnectionManager: tracks every currently-connected WebSocket client
and fans a message out to all of them.

Real-world analogy:
    This is the "who's watching the dashboard right now" registry. An
    HTTP request/response is a one-shot exchange; a WebSocket
    connection stays open, so the server needs to actively track which
    connections are alive to know who to push updates to - there's no
    equivalent bookkeeping needed for plain REST endpoints.
"""

from __future__ import annotations

from fastapi import WebSocket


class ConnectionManager:
    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        self._connections.discard(websocket)

    async def broadcast(self, message: dict) -> None:
        """
        Send one JSON message to every connected client. A client that
        fails to receive it (already gone, network dropped without a
        clean close handshake) is removed rather than letting one dead
        connection raise an exception that stops the broadcast to
        everyone else.
        """
        dead: list[WebSocket] = []
        for connection in list(self._connections):
            try:
                await connection.send_json(message)
            except Exception:
                dead.append(connection)

        for connection in dead:
            self.disconnect(connection)

    @property
    def connection_count(self) -> int:
        return len(self._connections)


# Module-level singleton - one registry shared by the WebSocket route
# and the background broadcaster, for the lifetime of the process.
manager = ConnectionManager()
