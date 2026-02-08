"""
Async file watcher that wraps the existing FileWatcher for use with FastAPI.

Runs the synchronous FileWatcher.run_once() in a thread and puts events
on an asyncio queue for broadcasting via WebSocket.
"""

import asyncio
import sqlite3
from datetime import date, datetime
from pathlib import Path
from typing import Any, Dict, Optional

from ccwap.etl.watcher import FileWatcher
from ccwap.server.websocket import ConnectionManager


def _query_latest_session(config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Query the most recently active session from the database.

    Uses its own synchronous connection (safe for asyncio.to_thread).
    Returns None if no sessions exist or on error.
    """
    try:
        from ccwap.config.loader import get_database_path
        db_path = get_database_path(config or {})
        if not Path(str(db_path)).exists():
            return None

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            cursor = conn.execute("""
                SELECT session_id, project_display, git_branch
                FROM sessions
                ORDER BY last_timestamp DESC
                LIMIT 1
            """)
            row = cursor.fetchone()
            if row:
                return {
                    "session_id": row["session_id"],
                    "project_display": row["project_display"] or "",
                    "git_branch": row["git_branch"] or "",
                }
        finally:
            conn.close()
    except Exception:
        pass
    return None


def _query_daily_cost(config: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
    """
    Query today's cost total and session count from daily_summaries.

    Uses its own synchronous connection (safe for asyncio.to_thread).
    Returns None if no data or on error.
    """
    try:
        from ccwap.config.loader import get_database_path
        db_path = get_database_path(config or {})
        if not Path(str(db_path)).exists():
            return None

        conn = sqlite3.connect(str(db_path))
        conn.row_factory = sqlite3.Row
        try:
            today = date.today().isoformat()
            cursor = conn.execute("""
                SELECT cost, sessions
                FROM daily_summaries
                WHERE date = ?
            """, (today,))
            row = cursor.fetchone()
            if row:
                return {
                    "cost_today": row["cost"] or 0.0,
                    "sessions_today": row["sessions"] or 0,
                }
            return {"cost_today": 0.0, "sessions_today": 0}
        finally:
            conn.close()
    except Exception:
        pass
    return None


async def run_daily_cost_broadcaster(
    manager: ConnectionManager,
    config: Optional[Dict[str, Any]] = None,
    interval: int = 30,
    stop_event: Optional[asyncio.Event] = None,
):
    """
    Background task that periodically broadcasts today's cost total.

    Runs every `interval` seconds and sends a daily_cost_update message
    to all connected WebSocket clients.

    Args:
        manager: WebSocket connection manager for broadcasting
        config: Configuration dict
        interval: Seconds between cost update broadcasts
        stop_event: Event to signal shutdown
    """
    stop = stop_event or asyncio.Event()

    while not stop.is_set():
        try:
            if manager.connection_count > 0:
                result = await asyncio.to_thread(_query_daily_cost, config)
                if result is not None:
                    event = {
                        "type": "daily_cost_update",
                        "timestamp": datetime.now().isoformat(),
                        "cost_today": result["cost_today"],
                        "sessions_today": result["sessions_today"],
                    }
                    await manager.broadcast(event)

            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass

        except Exception:
            try:
                await asyncio.wait_for(stop.wait(), timeout=interval)
                break
            except asyncio.TimeoutError:
                pass


async def run_file_watcher(
    manager: ConnectionManager,
    config: Optional[Dict[str, Any]] = None,
    poll_interval: int = 5,
    stop_event: Optional[asyncio.Event] = None,
):
    """
    Background task that polls for file changes and broadcasts via WebSocket.

    Uses asyncio.to_thread() to run the synchronous FileWatcher.run_once()
    without blocking the event loop. The FileWatcher gets its own sqlite3
    connection (NOT shared with aiosqlite).

    Args:
        manager: WebSocket connection manager for broadcasting
        config: Configuration dict
        poll_interval: Seconds between polls
        stop_event: Event to signal shutdown
    """
    stop = stop_event or asyncio.Event()
    watcher = FileWatcher(config=config, poll_interval=poll_interval, verbose=False)

    while not stop.is_set():
        try:
            # Only scan if there are connected clients
            if manager.connection_count > 0:
                result = await asyncio.to_thread(watcher.run_once)

                if result and result.get('files_changed', 0) > 0:
                    event = {
                        "type": "etl_update",
                        "timestamp": datetime.now().isoformat(),
                        "files_processed": result.get('files_processed', 0),
                        "turns_inserted": result.get('turns_inserted', 0),
                        "tool_calls_inserted": result.get('tool_calls_inserted', 0),
                        "entries_parsed": result.get('entries_parsed', 0),
                    }
                    await manager.broadcast(event)

                    # After ETL update, broadcast active session info
                    session_info = await asyncio.to_thread(
                        _query_latest_session, config
                    )
                    if session_info:
                        session_event = {
                            "type": "active_session",
                            "timestamp": datetime.now().isoformat(),
                            "session_id": session_info["session_id"],
                            "project_display": session_info["project_display"],
                            "git_branch": session_info["git_branch"],
                        }
                        await manager.broadcast(session_event)

            # Wait for poll_interval or until stopped
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
                break  # stop was set
            except asyncio.TimeoutError:
                pass  # Normal timeout, continue polling

        except Exception:
            # Don't crash the background task on errors
            try:
                await asyncio.wait_for(stop.wait(), timeout=poll_interval)
                break
            except asyncio.TimeoutError:
                pass
