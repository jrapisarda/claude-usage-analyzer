"""Test fixtures for server tests.

Creates a deterministic test database with known data for testing API endpoints.
Follows the existing ReportTestBase pattern from ccwap/tests/test_reports.py.
"""

import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

import pytest
import pytest_asyncio
import aiosqlite
from httpx import ASGITransport, AsyncClient

from ccwap.models.schema import get_connection, ensure_database
from ccwap.server.app import create_app


@pytest.fixture(scope="session")
def event_loop():
    """Create a session-scoped event loop."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def test_db_path(tmp_path):
    """Create a temporary database path."""
    return tmp_path / "test_server.db"


@pytest.fixture
def populated_db(test_db_path):
    """Create and populate a test database with deterministic data."""
    conn = get_connection(test_db_path)
    ensure_database(conn)
    _populate_test_data(conn)
    conn.close()
    return test_db_path


def _populate_test_data(conn):
    """Insert deterministic test data.

    Creates:
    - 3 projects with 5 sessions total
    - 10 turns with known costs and token counts
    - 8 tool calls with known success/error states
    - Daily summaries for 3 days
    - 1 experiment tag
    """
    now = datetime(2026, 2, 5, 12, 0, 0)
    yesterday = now - timedelta(days=1)
    two_days_ago = now - timedelta(days=2)

    # Sessions
    conn.execute("""
        INSERT INTO sessions (session_id, project_path, project_display,
            first_timestamp, last_timestamp, duration_seconds,
            is_agent, cc_version, git_branch, file_path)
        VALUES
            ('sess-001', '/path/proj-alpha', 'proj-alpha', ?, ?, 3600, 0, '1.0.23', 'main', '/logs/s1.jsonl'),
            ('sess-002', '/path/proj-alpha', 'proj-alpha', ?, ?, 1800, 0, '1.0.23', 'feat-x', '/logs/s2.jsonl'),
            ('sess-003', '/path/proj-beta', 'proj-beta', ?, ?, 900, 1, '1.0.24', 'main', '/logs/s3.jsonl'),
            ('sess-004', '/path/proj-beta', 'proj-beta', ?, ?, 600, 0, '1.0.24', 'main', '/logs/s4.jsonl'),
            ('sess-005', '/path/proj-gamma', 'proj-gamma', ?, ?, 1200, 0, '1.0.23', 'develop', '/logs/s5.jsonl')
    """, (
        now.isoformat(), now.isoformat(),
        yesterday.isoformat(), yesterday.isoformat(),
        yesterday.isoformat(), yesterday.isoformat(),
        two_days_ago.isoformat(), two_days_ago.isoformat(),
        two_days_ago.isoformat(), two_days_ago.isoformat(),
    ))

    # Turns: 10 turns with known costs
    conn.execute("""
        INSERT INTO turns (session_id, uuid, entry_type, timestamp,
            model, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            thinking_chars, cost, stop_reason, is_sidechain, is_meta,
            user_prompt_preview)
        VALUES
            ('sess-001', 'u01', 'user', ?, 'claude-opus-4-5-20251101', 100, 0, 50, 25, 0, 0.00, NULL, 0, 0, 'Fix the login bug'),
            ('sess-001', 'u02', 'assistant', ?, 'claude-opus-4-5-20251101', 200, 1000, 100, 50, 500, 0.10, 'end_turn', 0, 0, NULL),
            ('sess-001', 'u03', 'user', ?, 'claude-opus-4-5-20251101', 150, 0, 75, 30, 0, 0.00, NULL, 0, 0, 'Now add tests'),
            ('sess-001', 'u04', 'assistant', ?, 'claude-opus-4-5-20251101', 300, 2000, 200, 100, 1200, 0.20, 'end_turn', 0, 0, NULL),
            ('sess-002', 'u05', 'user', ?, 'claude-sonnet-4-20250514', 100, 0, 50, 20, 0, 0.00, NULL, 0, 0, 'Refactor the API'),
            ('sess-002', 'u06', 'assistant', ?, 'claude-sonnet-4-20250514', 200, 800, 100, 40, 300, 0.05, 'end_turn', 0, 0, NULL),
            ('sess-003', 'u07', 'assistant', ?, 'claude-haiku-4-5-20251001', 50, 250, 25, 10, 0, 0.01, 'end_turn', 1, 0, NULL),
            ('sess-004', 'u08', 'user', ?, 'claude-sonnet-4-20250514', 80, 0, 40, 15, 0, 0.00, NULL, 0, 0, 'Update readme'),
            ('sess-004', 'u09', 'assistant', ?, 'claude-sonnet-4-20250514', 150, 600, 80, 30, 200, 0.04, 'max_tokens', 0, 0, NULL),
            ('sess-005', 'u10', 'assistant', ?, 'claude-opus-4-5-20251101', 250, 1500, 150, 60, 800, 0.15, 'end_turn', 0, 1, NULL)
    """, (
        now.isoformat(), now.isoformat(), now.isoformat(), now.isoformat(),
        yesterday.isoformat(), yesterday.isoformat(),
        yesterday.isoformat(),
        two_days_ago.isoformat(), two_days_ago.isoformat(),
        two_days_ago.isoformat(),
    ))

    # Tool calls
    conn.execute("""
        INSERT INTO tool_calls (session_id, turn_id, tool_use_id, tool_name, timestamp,
            success, file_path, language, loc_written, lines_added, lines_deleted,
            error_message, error_category)
        VALUES
            ('sess-001', 2, 'tc01', 'Write', ?, 1, '/path/auth.py', 'python', 50, 50, 0, NULL, NULL),
            ('sess-001', 2, 'tc02', 'Read', ?, 1, '/path/models.py', 'python', 0, 0, 0, NULL, NULL),
            ('sess-001', 4, 'tc03', 'Write', ?, 1, '/path/test_auth.py', 'python', 80, 80, 0, NULL, NULL),
            ('sess-001', 4, 'tc04', 'Bash', ?, 0, NULL, NULL, 0, 0, 0, 'exit code 1', 'Exit code non-zero'),
            ('sess-002', 6, 'tc05', 'Edit', ?, 1, '/path/api.js', 'javascript', 20, 30, 10, NULL, NULL),
            ('sess-002', 6, 'tc06', 'Bash', ?, 1, NULL, NULL, 0, 0, 0, NULL, NULL),
            ('sess-004', 9, 'tc07', 'Write', ?, 1, '/path/README.md', 'markdown', 40, 40, 0, NULL, NULL),
            ('sess-005', 10, 'tc08', 'Edit', ?, 0, '/path/config.py', 'python', 0, 5, 3, 'Not unique', 'Not unique')
    """, (
        now.isoformat(), now.isoformat(), now.isoformat(), now.isoformat(),
        yesterday.isoformat(), yesterday.isoformat(),
        two_days_ago.isoformat(),
        two_days_ago.isoformat(),
    ))

    # Daily summaries (materialized)
    conn.execute("""
        INSERT INTO daily_summaries (date, sessions, messages, user_turns, tool_calls,
            errors, error_rate, loc_written, loc_delivered, lines_added, lines_deleted,
            files_created, files_edited, input_tokens, output_tokens, cache_read_tokens,
            cache_write_tokens, thinking_chars, cost, agent_spawns, skill_invocations)
        VALUES
            ('2026-02-05', 1, 4, 2, 4, 1, 0.25, 130, 130, 130, 0, 2, 0, 750, 3000, 425, 205, 1700, 0.30, 0, 0),
            ('2026-02-04', 2, 3, 1, 2, 0, 0.00, 20, 20, 30, 10, 0, 1, 350, 1050, 175, 70, 300, 0.06, 1, 0),
            ('2026-02-03', 2, 3, 1, 2, 1, 0.50, 40, 42, 45, 3, 1, 1, 480, 2100, 270, 105, 1000, 0.19, 0, 1)
    """)

    # Experiment tag
    conn.execute("""
        INSERT INTO experiment_tags (tag_name, session_id)
        VALUES ('baseline', 'sess-001'), ('baseline', 'sess-002')
    """)

    conn.commit()


@pytest_asyncio.fixture
async def async_db(populated_db):
    """Open an aiosqlite connection to the populated test database."""
    db = await aiosqlite.connect(str(populated_db))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    yield db
    await db.close()


@pytest_asyncio.fixture
async def client(populated_db):
    """Create an async test client with the populated database."""
    config = {
        "database_path": str(populated_db),
        "pricing": {
            "claude-opus-4-5-20251101": {"input": 15.0, "output": 75.0, "cache_read": 1.5, "cache_write": 18.75},
            "claude-sonnet-4-20250514": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
            "claude-haiku-4-5-20251001": {"input": 1.0, "output": 5.0, "cache_read": 0.1, "cache_write": 1.25},
            "default": {"input": 3.0, "output": 15.0, "cache_read": 0.3, "cache_write": 3.75},
        },
        "pricing_version": "2026-02-01",
        "snapshots_path": "~/.ccwap/snapshots",
        "claude_projects_path": "~/.claude/projects",
        "budget_alerts": {"daily_warning": None, "weekly_warning": None, "monthly_warning": None},
        "display": {"color_enabled": True, "progress_threshold_mb": 10, "table_max_width": 120},
    }

    app = create_app(config=config)

    # Override lifespan by manually setting up the database
    db = await aiosqlite.connect(str(populated_db))
    db.row_factory = aiosqlite.Row
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    app.state.db = db
    app.state.config = config

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    await db.close()
