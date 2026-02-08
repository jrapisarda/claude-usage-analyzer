"""Tests for the WebSocket ConnectionManager.

Validates connect, disconnect, broadcast, and connection_count behavior.
Uses mock WebSocket objects to avoid needing a real ASGI scope.
"""

import asyncio
import json
from unittest.mock import AsyncMock, MagicMock

import pytest

from ccwap.server.websocket import ConnectionManager


@pytest.fixture
def manager():
    """Create a fresh ConnectionManager instance."""
    return ConnectionManager()


def make_mock_ws():
    """Create a mock WebSocket with accept() and send_text() as async mocks."""
    ws = AsyncMock()
    ws.accept = AsyncMock()
    ws.send_text = AsyncMock()
    return ws


@pytest.mark.asyncio
class TestConnect:
    """Tests for ConnectionManager.connect()."""

    async def test_connect_calls_accept(self, manager):
        """connect() should call websocket.accept()."""
        ws = make_mock_ws()
        await manager.connect(ws)
        ws.accept.assert_awaited_once()

    async def test_connect_adds_to_active_connections(self, manager):
        """After connect(), the websocket should be in active_connections."""
        ws = make_mock_ws()
        await manager.connect(ws)
        assert ws in manager.active_connections

    async def test_connect_multiple_clients(self, manager):
        """Multiple websockets can connect simultaneously."""
        ws1 = make_mock_ws()
        ws2 = make_mock_ws()
        ws3 = make_mock_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.connect(ws3)
        assert len(manager.active_connections) == 3
        assert {ws1, ws2, ws3} == manager.active_connections

    async def test_connect_same_ws_twice_does_not_duplicate(self, manager):
        """Connecting the same websocket object twice keeps only one entry (set behavior)."""
        ws = make_mock_ws()
        await manager.connect(ws)
        await manager.connect(ws)
        assert len(manager.active_connections) == 1


@pytest.mark.asyncio
class TestDisconnect:
    """Tests for ConnectionManager.disconnect()."""

    async def test_disconnect_removes_from_active_connections(self, manager):
        """disconnect() should remove the websocket from the set."""
        ws = make_mock_ws()
        await manager.connect(ws)
        assert ws in manager.active_connections
        await manager.disconnect(ws)
        assert ws not in manager.active_connections

    async def test_disconnect_nonexistent_ws_does_not_raise(self, manager):
        """disconnect() with a ws not in the set should not raise (discard behavior)."""
        ws = make_mock_ws()
        # Should not raise even though ws was never connected
        await manager.disconnect(ws)

    async def test_disconnect_leaves_other_connections_intact(self, manager):
        """Disconnecting one ws does not affect others."""
        ws1 = make_mock_ws()
        ws2 = make_mock_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        await manager.disconnect(ws1)
        assert ws1 not in manager.active_connections
        assert ws2 in manager.active_connections


@pytest.mark.asyncio
class TestBroadcast:
    """Tests for ConnectionManager.broadcast()."""

    async def test_broadcast_sends_to_all_connected(self, manager):
        """broadcast() should send the JSON message to all connected clients."""
        ws1 = make_mock_ws()
        ws2 = make_mock_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)

        message = {"type": "etl_update", "files_processed": 3}
        await manager.broadcast(message)

        expected_data = json.dumps(message, default=str)
        ws1.send_text.assert_awaited_once_with(expected_data)
        ws2.send_text.assert_awaited_once_with(expected_data)

    async def test_broadcast_no_clients_does_nothing(self, manager):
        """broadcast() with no connected clients should return immediately."""
        # Should not raise or do anything
        await manager.broadcast({"type": "test"})

    async def test_broadcast_removes_disconnected_clients(self, manager):
        """If send_text raises, that client should be removed from active_connections."""
        ws_good = make_mock_ws()
        ws_bad = make_mock_ws()
        ws_bad.send_text = AsyncMock(side_effect=Exception("connection closed"))

        await manager.connect(ws_good)
        await manager.connect(ws_bad)

        message = {"type": "etl_update"}
        await manager.broadcast(message)

        # Bad ws should be removed
        assert ws_bad not in manager.active_connections
        # Good ws should remain
        assert ws_good in manager.active_connections

    async def test_broadcast_handles_all_clients_disconnected(self, manager):
        """If all clients fail during broadcast, the set should be empty after."""
        ws1 = make_mock_ws()
        ws1.send_text = AsyncMock(side_effect=RuntimeError("gone"))
        ws2 = make_mock_ws()
        ws2.send_text = AsyncMock(side_effect=ConnectionError("reset"))

        await manager.connect(ws1)
        await manager.connect(ws2)

        await manager.broadcast({"type": "test"})

        assert len(manager.active_connections) == 0

    async def test_broadcast_serializes_datetime_via_default_str(self, manager):
        """broadcast() uses default=str for JSON serialization (handles datetime)."""
        from datetime import datetime

        ws = make_mock_ws()
        await manager.connect(ws)

        now = datetime(2026, 2, 5, 12, 0, 0)
        message = {"type": "test", "timestamp": now}
        await manager.broadcast(message)

        sent_data = ws.send_text.call_args[0][0]
        parsed = json.loads(sent_data)
        assert parsed["timestamp"] == "2026-02-05 12:00:00"

    async def test_broadcast_sends_valid_json(self, manager):
        """The data sent via broadcast should be valid JSON."""
        ws = make_mock_ws()
        await manager.connect(ws)

        message = {"type": "etl_update", "files_processed": 5, "turns_inserted": 12}
        await manager.broadcast(message)

        sent_data = ws.send_text.call_args[0][0]
        parsed = json.loads(sent_data)
        assert parsed["type"] == "etl_update"
        assert parsed["files_processed"] == 5
        assert parsed["turns_inserted"] == 12


@pytest.mark.asyncio
class TestConnectionCount:
    """Tests for ConnectionManager.connection_count property."""

    async def test_connection_count_initially_zero(self, manager):
        """A new manager should have zero connections."""
        assert manager.connection_count == 0

    async def test_connection_count_after_connect(self, manager):
        """connection_count should reflect connected clients."""
        ws = make_mock_ws()
        await manager.connect(ws)
        assert manager.connection_count == 1

    async def test_connection_count_after_multiple_connects(self, manager):
        """connection_count should reflect the total number of unique connections."""
        for _ in range(5):
            await manager.connect(make_mock_ws())
        assert manager.connection_count == 5

    async def test_connection_count_after_disconnect(self, manager):
        """connection_count should decrease after disconnect."""
        ws1 = make_mock_ws()
        ws2 = make_mock_ws()
        await manager.connect(ws1)
        await manager.connect(ws2)
        assert manager.connection_count == 2

        await manager.disconnect(ws1)
        assert manager.connection_count == 1

    async def test_connection_count_after_broadcast_removes_dead(self, manager):
        """connection_count should decrease when broadcast removes dead clients."""
        ws_good = make_mock_ws()
        ws_bad = make_mock_ws()
        ws_bad.send_text = AsyncMock(side_effect=Exception("dead"))

        await manager.connect(ws_good)
        await manager.connect(ws_bad)
        assert manager.connection_count == 2

        await manager.broadcast({"type": "test"})
        assert manager.connection_count == 1
