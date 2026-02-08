"""Tests for the async file watcher that wraps FileWatcher for use with FastAPI.

Validates that run_file_watcher:
- Only polls when clients are connected
- Broadcasts etl_update events when files change
- Handles stop_event gracefully
- Handles FileWatcher errors without crashing
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from ccwap.server.websocket import ConnectionManager


@pytest.fixture
def manager():
    """Create a ConnectionManager with mocked broadcast."""
    mgr = ConnectionManager()
    mgr.broadcast = AsyncMock()
    return mgr


@pytest.fixture
def stop_event():
    """Create an asyncio.Event for signaling shutdown."""
    return asyncio.Event()


@pytest.mark.asyncio
class TestRunFileWatcher:
    """Tests for run_file_watcher()."""

    async def test_stops_when_stop_event_set(self, manager, stop_event):
        """run_file_watcher should exit gracefully when stop_event is set."""
        stop_event.set()

        with patch("ccwap.server.file_watcher.FileWatcher") as MockWatcher:
            MockWatcher.return_value = MagicMock()
            from ccwap.server.file_watcher import run_file_watcher

            # Should complete without hanging since stop_event is already set
            await asyncio.wait_for(
                run_file_watcher(manager, config={}, poll_interval=1, stop_event=stop_event),
                timeout=3.0,
            )

    async def test_skips_polling_when_no_clients(self, manager, stop_event):
        """run_file_watcher should not call run_once when connection_count is 0."""
        assert manager.connection_count == 0

        mock_watcher_instance = MagicMock()
        mock_watcher_instance.run_once = MagicMock(return_value={"files_changed": 0})

        with patch("ccwap.server.file_watcher.FileWatcher", return_value=mock_watcher_instance):
            from ccwap.server.file_watcher import run_file_watcher

            # Let it run for 2 poll intervals, then stop
            async def stop_after_delay():
                await asyncio.sleep(0.3)
                stop_event.set()

            await asyncio.gather(
                run_file_watcher(manager, config={}, poll_interval=0.1, stop_event=stop_event),
                stop_after_delay(),
            )

            # run_once should not have been called because no clients are connected
            mock_watcher_instance.run_once.assert_not_called()

    async def test_polls_when_clients_connected(self, manager, stop_event):
        """run_file_watcher should call run_once when clients are connected."""
        # Simulate a connected client by adding a mock ws
        mock_ws = AsyncMock()
        manager.active_connections.add(mock_ws)

        mock_watcher_instance = MagicMock()
        mock_watcher_instance.run_once = MagicMock(return_value={"files_changed": 0})

        with patch("ccwap.server.file_watcher.FileWatcher", return_value=mock_watcher_instance):
            from ccwap.server.file_watcher import run_file_watcher

            async def stop_after_delay():
                await asyncio.sleep(0.3)
                stop_event.set()

            await asyncio.gather(
                run_file_watcher(manager, config={}, poll_interval=0.1, stop_event=stop_event),
                stop_after_delay(),
            )

            # run_once should have been called at least once
            assert mock_watcher_instance.run_once.call_count >= 1

    async def test_broadcasts_etl_update_when_files_changed(self, manager, stop_event):
        """When files_changed > 0, should broadcast an etl_update event."""
        mock_ws = AsyncMock()
        manager.active_connections.add(mock_ws)

        watcher_result = {
            "files_changed": 2,
            "files_processed": 2,
            "turns_inserted": 15,
            "tool_calls_inserted": 8,
            "entries_parsed": 50,
        }
        mock_watcher_instance = MagicMock()
        mock_watcher_instance.run_once = MagicMock(return_value=watcher_result)

        with patch("ccwap.server.file_watcher.FileWatcher", return_value=mock_watcher_instance):
            from ccwap.server.file_watcher import run_file_watcher

            async def stop_after_one_poll():
                await asyncio.sleep(0.15)
                stop_event.set()

            await asyncio.gather(
                run_file_watcher(manager, config={}, poll_interval=0.1, stop_event=stop_event),
                stop_after_one_poll(),
            )

            # broadcast should have been called with an etl_update event
            assert manager.broadcast.call_count >= 1
            call_args = manager.broadcast.call_args_list[0][0][0]
            assert call_args["type"] == "etl_update"
            assert call_args["files_processed"] == 2
            assert call_args["turns_inserted"] == 15
            assert call_args["tool_calls_inserted"] == 8
            assert call_args["entries_parsed"] == 50
            assert "timestamp" in call_args

    async def test_does_not_broadcast_when_no_changes(self, manager, stop_event):
        """When files_changed is 0, should NOT broadcast."""
        mock_ws = AsyncMock()
        manager.active_connections.add(mock_ws)

        mock_watcher_instance = MagicMock()
        mock_watcher_instance.run_once = MagicMock(
            return_value={"files_changed": 0, "message": "No changes detected"}
        )

        with patch("ccwap.server.file_watcher.FileWatcher", return_value=mock_watcher_instance):
            from ccwap.server.file_watcher import run_file_watcher

            async def stop_after_delay():
                await asyncio.sleep(0.3)
                stop_event.set()

            await asyncio.gather(
                run_file_watcher(manager, config={}, poll_interval=0.1, stop_event=stop_event),
                stop_after_delay(),
            )

            manager.broadcast.assert_not_called()

    async def test_does_not_broadcast_when_result_is_none(self, manager, stop_event):
        """If run_once returns None, should not broadcast."""
        mock_ws = AsyncMock()
        manager.active_connections.add(mock_ws)

        mock_watcher_instance = MagicMock()
        mock_watcher_instance.run_once = MagicMock(return_value=None)

        with patch("ccwap.server.file_watcher.FileWatcher", return_value=mock_watcher_instance):
            from ccwap.server.file_watcher import run_file_watcher

            async def stop_after_delay():
                await asyncio.sleep(0.2)
                stop_event.set()

            await asyncio.gather(
                run_file_watcher(manager, config={}, poll_interval=0.1, stop_event=stop_event),
                stop_after_delay(),
            )

            manager.broadcast.assert_not_called()

    async def test_handles_watcher_exception_without_crashing(self, manager, stop_event):
        """If FileWatcher.run_once raises, the watcher should continue running."""
        mock_ws = AsyncMock()
        manager.active_connections.add(mock_ws)

        call_count = 0

        def run_once_with_error():
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise RuntimeError("Simulated file watcher error")
            return {"files_changed": 0}

        mock_watcher_instance = MagicMock()
        mock_watcher_instance.run_once = MagicMock(side_effect=run_once_with_error)

        with patch("ccwap.server.file_watcher.FileWatcher", return_value=mock_watcher_instance):
            from ccwap.server.file_watcher import run_file_watcher

            async def stop_after_delay():
                await asyncio.sleep(0.4)
                stop_event.set()

            # Should not raise even though run_once throws on first call
            await asyncio.gather(
                run_file_watcher(manager, config={}, poll_interval=0.1, stop_event=stop_event),
                stop_after_delay(),
            )

            # Should have been called more than once (recovered after the error)
            assert call_count >= 2

    async def test_uses_configured_poll_interval(self, manager, stop_event):
        """The watcher should respect the poll_interval parameter."""
        mock_ws = AsyncMock()
        manager.active_connections.add(mock_ws)

        mock_watcher_instance = MagicMock()
        mock_watcher_instance.run_once = MagicMock(return_value={"files_changed": 0})

        with patch("ccwap.server.file_watcher.FileWatcher", return_value=mock_watcher_instance):
            from ccwap.server.file_watcher import run_file_watcher

            # Use a longer poll interval so we only get ~1 poll in the test window
            async def stop_after_delay():
                await asyncio.sleep(0.35)
                stop_event.set()

            await asyncio.gather(
                run_file_watcher(manager, config={}, poll_interval=0.2, stop_event=stop_event),
                stop_after_delay(),
            )

            # With a 0.2s interval and 0.35s total, should get 1-2 polls
            assert 1 <= mock_watcher_instance.run_once.call_count <= 2

    async def test_creates_file_watcher_with_config(self, stop_event):
        """FileWatcher should be instantiated with the provided config."""
        mgr = ConnectionManager()
        stop_event.set()

        test_config = {"database_path": "/tmp/test.db"}

        with patch("ccwap.server.file_watcher.FileWatcher") as MockWatcher:
            MockWatcher.return_value = MagicMock()
            from ccwap.server.file_watcher import run_file_watcher

            await run_file_watcher(
                mgr, config=test_config, poll_interval=1, stop_event=stop_event
            )

            MockWatcher.assert_called_once_with(
                config=test_config, poll_interval=1, verbose=False
            )
