"""
WebSocket connection manager for live monitoring.

Manages active WebSocket connections and broadcasts events to all clients.
"""

import asyncio
import json
from datetime import datetime
from typing import Any, Dict

from fastapi import WebSocket


class ConnectionManager:
    """Manages WebSocket connections for live monitoring."""

    def __init__(self):
        self.active_connections: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, websocket: WebSocket):
        """Accept and register a new WebSocket connection."""
        await websocket.accept()
        async with self._lock:
            self.active_connections.add(websocket)

    async def disconnect(self, websocket: WebSocket):
        """Remove a WebSocket connection."""
        async with self._lock:
            self.active_connections.discard(websocket)

    async def broadcast(self, message: Dict[str, Any]):
        """Send a message to all connected clients."""
        if not self.active_connections:
            return

        data = json.dumps(message, default=str)
        disconnected = set()

        async with self._lock:
            for ws in self.active_connections:
                try:
                    await ws.send_text(data)
                except Exception:
                    disconnected.add(ws)

            self.active_connections -= disconnected

    @property
    def connection_count(self) -> int:
        return len(self.active_connections)
