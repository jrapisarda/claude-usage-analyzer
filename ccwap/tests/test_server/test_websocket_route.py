"""Tests for the WebSocket endpoint /ws/live in the FastAPI app.

Uses starlette.testclient.TestClient for synchronous WebSocket testing.
The TestClient handles the ASGI scope setup that WebSocket connections need.
"""

import json

import pytest
import aiosqlite
from starlette.testclient import TestClient

from ccwap.server.app import create_app
from ccwap.server.websocket import ConnectionManager


@pytest.fixture
def app_with_ws_manager(populated_db):
    """Create an app with ws_manager set up (bypassing full lifespan)."""
    config = {
        "database_path": str(populated_db),
        "pricing": {
            "claude-opus-4-5-20251101": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
            "default": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
        },
        "pricing_version": "2026-02-01",
        "snapshots_path": "~/.ccwap/snapshots",
        "claude_projects_path": "~/.claude/projects",
        "budget_alerts": {"daily_warning": None, "weekly_warning": None, "monthly_warning": None},
        "display": {"color_enabled": True, "progress_threshold_mb": 10, "table_max_width": 120},
    }
    app = create_app(config=config)

    # Manually set up the ws_manager since we bypass lifespan
    manager = ConnectionManager()
    app.state.ws_manager = manager
    app.state.config = config

    return app, manager


class TestWebSocketEndpoint:
    """Tests for the /ws/live WebSocket endpoint."""

    def test_websocket_connect_and_receive_pong(self, app_with_ws_manager):
        """Client should be able to connect and receive pong in response to ping."""
        app, manager = app_with_ws_manager

        with TestClient(app) as client:
            with client.websocket_connect("/ws/live") as ws:
                # Send a ping
                ws.send_text("ping")
                # Should receive a pong response
                data = ws.receive_text()
                parsed = json.loads(data)
                assert parsed["type"] == "pong"

    def test_websocket_multiple_pings(self, app_with_ws_manager):
        """Multiple ping/pong exchanges should work correctly."""
        app, manager = app_with_ws_manager

        with TestClient(app) as client:
            with client.websocket_connect("/ws/live") as ws:
                for _ in range(3):
                    ws.send_text("ping")
                    data = ws.receive_text()
                    parsed = json.loads(data)
                    assert parsed["type"] == "pong"

    def test_websocket_disconnect_handling(self, app_with_ws_manager):
        """After disconnect, the connection should be cleaned up."""
        app, manager = app_with_ws_manager

        with TestClient(app) as client:
            with client.websocket_connect("/ws/live") as ws:
                ws.send_text("ping")
                ws.receive_text()
                # Connection will be closed when exiting the context manager

        # After disconnect, the manager should have 0 connections
        # (TestClient handles the disconnect)
        assert manager.connection_count == 0
