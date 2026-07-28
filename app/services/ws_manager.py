"""WebSocket connection manager for live call-list updates.

Broadcasts ``call.created`` / ``call.updated`` events (per CONTRACT) to every
connected client. The dashboard is expected to fall back to polling if the
socket disconnects, so this manager intentionally does no buffering/replay —
it is fire-and-forget best effort.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import WebSocket

logger = logging.getLogger("gnani.ws")


class WebSocketManager:
    """Tracks connected WebSocket clients and broadcasts JSON events to them."""

    def __init__(self) -> None:
        self._connections: set[WebSocket] = set()

    async def connect(self, websocket: WebSocket) -> None:
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        self._connections.add(websocket)

    def disconnect(self, websocket: WebSocket) -> None:
        """Remove a WebSocket connection (call on disconnect/error)."""
        self._connections.discard(websocket)

    async def broadcast(self, message: dict[str, Any]) -> None:
        """Send a JSON message to every connected client, dropping dead sockets."""
        stale: list[WebSocket] = []
        for connection in self._connections:
            try:
                await connection.send_json(message)
            except Exception:
                logger.info("ws_send_failed_dropping_connection")
                stale.append(connection)
        for connection in stale:
            self.disconnect(connection)


ws_manager = WebSocketManager()
