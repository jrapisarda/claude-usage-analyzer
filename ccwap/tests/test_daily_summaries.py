"""Tests for daily_summaries materialization, user_prompt_preview, and schema migration."""

import unittest
import sqlite3
import tempfile
from pathlib import Path
from datetime import datetime, timedelta

from ccwap.models.schema import (
    ensure_database, get_connection, get_schema_version,
    set_schema_version, _create_initial_schema, _migrate_v1_to_v2,
    _migrate_v2_to_v3, CURRENT_SCHEMA_VERSION,
)
from ccwap.etl.loader import (
    materialize_daily_summaries,
    upsert_turns_batch,
    refresh_materialized_analytics_tables,
)
from ccwap.etl.extractor import extract_turn_data
from ccwap.models.entities import TurnData, TokenUsage
from ccwap.config.loader import load_config


class TestDailySummariesMaterialization(unittest.TestCase):
    """Test daily_summaries table materialization from turns and tool_calls."""

    def setUp(self):
        """Create test database with known data."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / 'test.db'
        self.conn = get_connection(self.db_path)
        ensure_database(self.conn)
        self._populate_test_data()

    def tearDown(self):
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _populate_test_data(self):
        """Insert deterministic test data spanning 3 days."""
        self.today = datetime.now().replace(hour=12, minute=0, second=0, microsecond=0)
        self.yesterday = self.today - timedelta(days=1)
        self.two_days_ago = self.today - timedelta(days=2)

        # Sessions: 2 today, 1 yesterday, 1 two_days_ago (agent)
        self.conn.execute("""
            INSERT INTO sessions (session_id, project_path, project_display,
                first_timestamp, last_timestamp, duration_seconds, is_agent, file_path)
            VALUES
                ('s1', '/p1', 'P1', ?, ?, 3600, 0, '/f1.jsonl'),
                ('s2', '/p1', 'P1', ?, ?, 1800, 0, '/f2.jsonl'),
                ('s3', '/p2', 'P2', ?, ?, 900, 0, '/f3.jsonl'),
                ('s4', '/p2', 'P2', ?, ?, 600, 1, '/f4.jsonl')
        """, (
            self.today.isoformat(), self.today.isoformat(),
            self.today.isoformat(), self.today.isoformat(),
            self.yesterday.isoformat(), self.yesterday.isoformat(),
            self.two_days_ago.isoformat(), self.two_days_ago.isoformat(),
        ))

        # Turns: Known token counts and costs
        # Today: 3 turns (2 in s1, 1 in s2)
        # Yesterday: 2 turns (in s3)
        # Two days ago: 1 turn (in s4, is_meta=1)
        self.conn.execute("""
            INSERT INTO turns (session_id, uuid, entry_type, timestamp,
                model, input_tokens, output_tokens, cache_read_tokens,
                cache_write_tokens, thinking_chars, cost, is_meta)
            VALUES
                ('s1', 'u1', 'user', ?, 'claude-opus-4-5-20251101', 100, 500, 50, 25, 0, 0.05, 0),
                ('s1', 'u2', 'assistant', ?, 'claude-opus-4-5-20251101', 200, 1000, 100, 50, 500, 0.10, 0),
                ('s2', 'u3', 'user', ?, 'claude-sonnet-4-20250514', 150, 750, 75, 30, 0, 0.03, 0),
                ('s3', 'u4', 'user', ?, 'claude-sonnet-4-20250514', 300, 1500, 150, 60, 0, 0.06, 0),
                ('s3', 'u5', 'assistant', ?, 'claude-sonnet-4-20250514', 400, 2000, 200, 80, 1000, 0.08, 0),
                ('s4', 'u6', 'assistant', ?, 'claude-haiku-3-5-20241022', 50, 250, 25, 10, 0, 0.01, 1)
        """, (
            self.today.isoformat(), self.today.isoformat(), self.today.isoformat(),
            self.yesterday.isoformat(), self.yesterday.isoformat(),
            self.two_days_ago.isoformat(),
        ))

        # Tool calls: Known counts and LOC
        # Today: 3 tool calls (2 in s1/turn 2, 1 in s2/turn 3), 1 error
        # Yesterday: 2 tool calls (in s3/turn 4), 0 errors
        # Two days ago: 1 tool call (in s4/turn 5), 0 errors
        self.conn.execute("""
            INSERT INTO tool_calls (session_id, turn_id, tool_name, timestamp,
                success, file_path, language, loc_written, lines_added, lines_deleted)
            VALUES
                ('s1', 2, 'Write', ?, 1, '/f.py', 'python', 50, 50, 0),
                ('s1', 2, 'Read', ?, 1, '/g.py', 'python', 0, 0, 0),
                ('s2', 3, 'Bash', ?, 0, NULL, NULL, 0, 0, 0),
                ('s3', 4, 'Write', ?, 1, '/h.js', 'javascript', 30, 30, 0),
                ('s3', 4, 'Edit', ?, 1, '/h.js', 'javascript', 10, 15, 5),
                ('s4', 5, 'Read', ?, 1, '/i.py', 'python', 0, 0, 0)
        """, (
            self.today.isoformat(), self.today.isoformat(), self.today.isoformat(),
            self.yesterday.isoformat(), self.yesterday.isoformat(),
            self.two_days_ago.isoformat(),
        ))

        self.conn.commit()

    def test_materialize_all_dates(self):
        """Full materialization produces correct row count."""
        count = materialize_daily_summaries(self.conn)
        self.conn.commit()
        self.assertEqual(count, 3)  # 3 distinct dates

    def test_today_sessions_count(self):
        """Today should have 2 sessions."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT sessions FROM daily_summaries WHERE date = ?", (today_str,)
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 2)

    def test_today_messages_count(self):
        """Today should have 3 messages (turns)."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT messages FROM daily_summaries WHERE date = ?", (today_str,)
        ).fetchone()
        self.assertEqual(row[0], 3)

    def test_today_user_turns_count(self):
        """Today should have 2 user turns."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT user_turns FROM daily_summaries WHERE date = ?", (today_str,)
        ).fetchone()
        self.assertEqual(row[0], 2)

    def test_today_token_aggregates(self):
        """Today's token totals should match hand-calculated values."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT input_tokens, output_tokens, cache_read_tokens, cache_write_tokens "
            "FROM daily_summaries WHERE date = ?", (today_str,)
        ).fetchone()
        # u1: 100+500+50+25, u2: 200+1000+100+50, u3: 150+750+75+30
        self.assertEqual(row[0], 100 + 200 + 150)  # input_tokens = 450
        self.assertEqual(row[1], 500 + 1000 + 750)  # output_tokens = 2250
        self.assertEqual(row[2], 50 + 100 + 75)     # cache_read = 225
        self.assertEqual(row[3], 25 + 50 + 30)      # cache_write = 105

    def test_today_cost(self):
        """Today's cost should sum correctly."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT cost FROM daily_summaries WHERE date = ?", (today_str,)
        ).fetchone()
        expected = 0.05 + 0.10 + 0.03
        self.assertAlmostEqual(row[0], expected, places=4)

    def test_today_tool_calls_and_errors(self):
        """Today should have 3 tool calls, 1 error."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT tool_calls, errors, error_rate FROM daily_summaries WHERE date = ?",
            (today_str,)
        ).fetchone()
        self.assertEqual(row[0], 3)
        self.assertEqual(row[1], 1)
        self.assertAlmostEqual(row[2], 1.0 / 3.0, places=4)

    def test_today_loc_metrics(self):
        """Today's LOC metrics should match."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT loc_written, lines_added, lines_deleted, loc_delivered "
            "FROM daily_summaries WHERE date = ?", (today_str,)
        ).fetchone()
        self.assertEqual(row[0], 50)  # loc_written (Write only)
        self.assertEqual(row[1], 50)  # lines_added
        self.assertEqual(row[2], 0)   # lines_deleted
        self.assertEqual(row[3], 50)  # loc_delivered = 50 - 0

    def test_today_files_created_edited(self):
        """Today's file counts should match."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT files_created, files_edited FROM daily_summaries WHERE date = ?",
            (today_str,)
        ).fetchone()
        self.assertEqual(row[0], 1)  # 1 Write to /f.py
        self.assertEqual(row[1], 0)  # no Edits today

    def test_yesterday_metrics(self):
        """Yesterday should have correct aggregates."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        yesterday_str = self.yesterday.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT sessions, messages, tool_calls, errors, loc_written, "
            "lines_added, lines_deleted, cost "
            "FROM daily_summaries WHERE date = ?", (yesterday_str,)
        ).fetchone()
        self.assertEqual(row[0], 1)   # 1 session
        self.assertEqual(row[1], 2)   # 2 turns
        self.assertEqual(row[2], 2)   # 2 tool calls
        self.assertEqual(row[3], 0)   # 0 errors
        self.assertEqual(row[4], 40)  # loc_written = 30 + 10
        self.assertEqual(row[5], 45)  # lines_added = 30 + 15
        self.assertEqual(row[6], 5)   # lines_deleted = 5
        self.assertAlmostEqual(row[7], 0.14, places=4)  # cost = 0.06 + 0.08

    def test_two_days_ago_agent_spawns(self):
        """Two days ago should count 1 agent spawn."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        tda_str = self.two_days_ago.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT agent_spawns, skill_invocations FROM daily_summaries WHERE date = ?",
            (tda_str,)
        ).fetchone()
        self.assertEqual(row[0], 1)  # 1 agent session
        self.assertEqual(row[1], 1)  # 1 is_meta turn

    def test_thinking_chars(self):
        """Thinking chars should aggregate correctly."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT thinking_chars FROM daily_summaries WHERE date = ?", (today_str,)
        ).fetchone()
        self.assertEqual(row[0], 500)  # only u2 has 500 thinking_chars

    def test_incremental_update_preserves_data(self):
        """Running materialization twice produces same results (idempotent)."""
        materialize_daily_summaries(self.conn)
        self.conn.commit()

        # Run again
        count = materialize_daily_summaries(self.conn)
        self.conn.commit()

        self.assertEqual(count, 3)
        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT cost FROM daily_summaries WHERE date = ?", (today_str,)
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.18, places=4)

    def test_affected_dates_filter(self):
        """Passing affected_dates only recomputes those dates."""
        today_str = self.today.strftime('%Y-%m-%d')
        count = materialize_daily_summaries(self.conn, affected_dates=[today_str])
        self.conn.commit()

        self.assertEqual(count, 1)
        # Today should exist
        row = self.conn.execute(
            "SELECT sessions FROM daily_summaries WHERE date = ?", (today_str,)
        ).fetchone()
        self.assertIsNotNone(row)
        # Yesterday should NOT exist
        yesterday_str = self.yesterday.strftime('%Y-%m-%d')
        row = self.conn.execute(
            "SELECT sessions FROM daily_summaries WHERE date = ?", (yesterday_str,)
        ).fetchone()
        self.assertIsNone(row)

    def test_empty_database(self):
        """Materialization on empty DB produces 0 rows."""
        # Use a fresh empty DB
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'empty.db'
        conn = get_connection(db_path)
        ensure_database(conn)

        count = materialize_daily_summaries(conn)
        conn.commit()
        self.assertEqual(count, 0)

        conn.close()
        db_path.unlink()

    def test_refresh_materialized_populates_loc_by_model(self):
        """Materialized tool_calls aggregate should include LOC grouped by model."""
        refresh_materialized_analytics_tables(self.conn)
        self.conn.commit()

        today_str = self.today.strftime('%Y-%m-%d')
        row = self.conn.execute("""
            SELECT COALESCE(SUM(loc_written), 0)
            FROM tool_calls_agg_daily
            WHERE date = ? AND model = 'claude-opus-4-5-20251101'
        """, (today_str,)).fetchone()

        # Today fixture has one Write with 50 LOC on Opus model.
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 50)


class TestDailySummariesEdgeCases(unittest.TestCase):
    """Test daily_summaries materialization edge cases."""

    def setUp(self):
        """Create a fresh test database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / 'test_edge.db'
        self.conn = get_connection(self.db_path)
        ensure_database(self.conn)

    def tearDown(self):
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _insert_session(self, session_id, timestamp, is_agent=0):
        """Helper to insert a minimal session."""
        self.conn.execute("""
            INSERT INTO sessions (session_id, project_path, first_timestamp,
                is_agent, file_path)
            VALUES (?, '/proj', ?, ?, '/f.jsonl')
        """, (session_id, timestamp, is_agent))

    def _insert_turn(self, session_id, uuid, entry_type, timestamp, **kwargs):
        """Helper to insert a minimal turn with optional overrides."""
        self.conn.execute("""
            INSERT INTO turns (session_id, uuid, entry_type, timestamp,
                input_tokens, output_tokens, cache_read_tokens,
                cache_write_tokens, thinking_chars, cost, is_meta)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, uuid, entry_type, timestamp,
            kwargs.get('input_tokens', 0),
            kwargs.get('output_tokens', 0),
            kwargs.get('cache_read_tokens', 0),
            kwargs.get('cache_write_tokens', 0),
            kwargs.get('thinking_chars', 0),
            kwargs.get('cost', 0.0),
            kwargs.get('is_meta', 0),
        ))

    def _insert_tool_call(self, session_id, turn_id, tool_name, timestamp, **kwargs):
        """Helper to insert a minimal tool_call with optional overrides."""
        self.conn.execute("""
            INSERT INTO tool_calls (session_id, turn_id, tool_name, timestamp,
                success, file_path, loc_written, lines_added, lines_deleted)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            session_id, turn_id, tool_name, timestamp,
            kwargs.get('success', 1),
            kwargs.get('file_path'),
            kwargs.get('loc_written', 0),
            kwargs.get('lines_added', 0),
            kwargs.get('lines_deleted', 0),
        ))

    def test_negative_loc_delivered(self):
        """loc_delivered should be negative when lines_deleted exceeds lines_added."""
        ts = '2026-01-20T12:00:00'
        self._insert_session('s1', ts)
        self._insert_turn('s1', 'u1', 'user', ts, cost=0.01)
        # Edit that deletes more than it adds
        self._insert_tool_call('s1', 1, 'Edit', ts,
                               lines_added=5, lines_deleted=20, file_path='/a.py')
        self.conn.commit()

        materialize_daily_summaries(self.conn)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT loc_delivered, lines_added, lines_deleted "
            "FROM daily_summaries WHERE date = '2026-01-20'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 5 - 20)  # loc_delivered = -15
        self.assertEqual(row[1], 5)
        self.assertEqual(row[2], 20)

    def test_turns_only_date_no_tool_calls(self):
        """A date with turns but no tool_calls should still appear with zero tool metrics."""
        ts = '2026-01-21T10:00:00'
        self._insert_session('s1', ts)
        self._insert_turn('s1', 'u1', 'user', ts, input_tokens=100, cost=0.02)
        self.conn.commit()

        materialize_daily_summaries(self.conn)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT sessions, messages, tool_calls, errors, error_rate, loc_written "
            "FROM daily_summaries WHERE date = '2026-01-21'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 1)    # 1 session
        self.assertEqual(row[1], 1)    # 1 message
        self.assertEqual(row[2], 0)    # 0 tool_calls
        self.assertEqual(row[3], 0)    # 0 errors
        self.assertAlmostEqual(row[4], 0.0)  # error_rate = 0 (no division by zero)
        self.assertEqual(row[5], 0)    # 0 loc_written

    def test_tool_calls_only_date_no_turns(self):
        """A date with tool_calls but no turns should appear with zero turn metrics.

        This scenario can happen if tool_call timestamps differ from turn timestamps
        (e.g., a tool_call at midnight belonging to a turn from the previous day).
        """
        # Insert session and turn on day 1
        day1 = '2026-01-22T23:59:00'
        day2 = '2026-01-23T00:01:00'
        self._insert_session('s1', day1)
        self._insert_turn('s1', 'u1', 'assistant', day1, output_tokens=500, cost=0.05)
        # Tool call timestamp falls on day 2
        self._insert_tool_call('s1', 1, 'Write', day2,
                               loc_written=30, lines_added=30, file_path='/x.py')
        self.conn.commit()

        materialize_daily_summaries(self.conn)
        self.conn.commit()

        # Day 2 should exist with tool_call data but zero turn data
        row = self.conn.execute(
            "SELECT sessions, messages, tool_calls, loc_written, cost "
            "FROM daily_summaries WHERE date = '2026-01-23'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 0)    # 0 sessions from turns
        self.assertEqual(row[1], 0)    # 0 messages
        self.assertEqual(row[2], 1)    # 1 tool_call
        self.assertEqual(row[3], 30)   # loc_written from tool_call
        self.assertEqual(row[4], 0)    # 0 cost (no turns)

    def test_multiple_affected_dates_filter(self):
        """affected_dates with multiple dates should recompute only those dates."""
        d1 = '2026-01-24T12:00:00'
        d2 = '2026-01-25T12:00:00'
        d3 = '2026-01-26T12:00:00'
        self._insert_session('s1', d1)
        self._insert_session('s2', d2)
        self._insert_session('s3', d3)
        self._insert_turn('s1', 'u1', 'user', d1, cost=0.01)
        self._insert_turn('s2', 'u2', 'user', d2, cost=0.02)
        self._insert_turn('s3', 'u3', 'user', d3, cost=0.03)
        self.conn.commit()

        count = materialize_daily_summaries(
            self.conn, affected_dates=['2026-01-24', '2026-01-26']
        )
        self.conn.commit()

        self.assertEqual(count, 2)
        # Day 1 and 3 should exist
        row1 = self.conn.execute(
            "SELECT cost FROM daily_summaries WHERE date = '2026-01-24'"
        ).fetchone()
        row3 = self.conn.execute(
            "SELECT cost FROM daily_summaries WHERE date = '2026-01-26'"
        ).fetchone()
        self.assertIsNotNone(row1)
        self.assertIsNotNone(row3)
        # Day 2 should NOT exist
        row2 = self.conn.execute(
            "SELECT cost FROM daily_summaries WHERE date = '2026-01-25'"
        ).fetchone()
        self.assertIsNone(row2)

    def test_replace_updates_existing_row(self):
        """INSERT OR REPLACE should update an existing daily_summaries row on re-materialization."""
        ts = '2026-01-27T12:00:00'
        self._insert_session('s1', ts)
        self._insert_turn('s1', 'u1', 'user', ts, cost=0.10)
        self.conn.commit()

        materialize_daily_summaries(self.conn)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT cost FROM daily_summaries WHERE date = '2026-01-27'"
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.10, places=4)

        # Add another turn for the same day
        self._insert_turn('s1', 'u2', 'assistant', ts, cost=0.20)
        self.conn.commit()

        # Re-materialize
        materialize_daily_summaries(self.conn)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT cost FROM daily_summaries WHERE date = '2026-01-27'"
        ).fetchone()
        self.assertAlmostEqual(row[0], 0.30, places=4)

    def test_turns_timestamp_not_null_constraint(self):
        """Turns table enforces NOT NULL on timestamp, preventing NULL aggregation issues."""
        ts = '2026-01-28T12:00:00'
        self._insert_session('s1', ts)
        # Attempting to insert a turn with NULL timestamp should raise IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("""
                INSERT INTO turns (session_id, uuid, entry_type, timestamp,
                    input_tokens, output_tokens, cost, is_meta)
                VALUES ('s1', 'u-null', 'user', NULL, 100, 200, 0.99, 0)
            """)

    def test_single_session_single_turn(self):
        """Minimal scenario: one session, one turn, no tool_calls."""
        ts = '2026-01-28T12:00:00'
        self._insert_session('s1', ts)
        self._insert_turn('s1', 'u1', 'user', ts,
                          input_tokens=50, output_tokens=100, cost=0.02)
        self.conn.commit()

        count = materialize_daily_summaries(self.conn)
        self.conn.commit()

        self.assertEqual(count, 1)
        row = self.conn.execute(
            "SELECT sessions, messages, user_turns, input_tokens, output_tokens, cost "
            "FROM daily_summaries WHERE date = '2026-01-28'"
        ).fetchone()
        self.assertEqual(row[0], 1)    # sessions
        self.assertEqual(row[1], 1)    # messages
        self.assertEqual(row[2], 1)    # user_turns
        self.assertEqual(row[3], 50)   # input_tokens
        self.assertEqual(row[4], 100)  # output_tokens
        self.assertAlmostEqual(row[5], 0.02, places=4)

    def test_null_timestamp_tool_calls_excluded(self):
        """Tool calls with NULL timestamp should not appear in daily_summaries."""
        ts = '2026-01-29T12:00:00'
        self._insert_session('s1', ts)
        self._insert_turn('s1', 'u1', 'assistant', ts, cost=0.01)
        # One tool_call with valid timestamp, one with NULL
        self._insert_tool_call('s1', 1, 'Write', ts,
                               loc_written=10, lines_added=10, file_path='/a.py')
        self.conn.execute("""
            INSERT INTO tool_calls (session_id, turn_id, tool_name, timestamp,
                success, loc_written, lines_added, lines_deleted)
            VALUES ('s1', 1, 'Write', NULL, 1, 999, 999, 0)
        """)
        self.conn.commit()

        materialize_daily_summaries(self.conn)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT tool_calls, loc_written FROM daily_summaries WHERE date = '2026-01-29'"
        ).fetchone()
        self.assertIsNotNone(row)
        self.assertEqual(row[0], 1)    # only the non-NULL tool_call
        self.assertEqual(row[1], 10)   # not 999+10

    def test_zero_tool_calls_error_rate_is_zero(self):
        """error_rate should be 0.0 when tool_calls is 0 (no division by zero)."""
        ts = '2026-01-30T12:00:00'
        self._insert_session('s1', ts)
        self._insert_turn('s1', 'u1', 'user', ts, cost=0.01)
        self.conn.commit()

        materialize_daily_summaries(self.conn)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT tool_calls, error_rate FROM daily_summaries WHERE date = '2026-01-30'"
        ).fetchone()
        self.assertEqual(row[0], 0)
        self.assertAlmostEqual(row[1], 0.0)

    def test_yesterday_loc_delivered_positive(self):
        """loc_delivered = lines_added - lines_deleted when positive."""
        ts = '2026-02-01T12:00:00'
        self._insert_session('s1', ts)
        self._insert_turn('s1', 'u1', 'assistant', ts)
        self._insert_tool_call('s1', 1, 'Edit', ts,
                               lines_added=100, lines_deleted=30, file_path='/b.py')
        self.conn.commit()

        materialize_daily_summaries(self.conn)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT loc_delivered FROM daily_summaries WHERE date = '2026-02-01'"
        ).fetchone()
        self.assertEqual(row[0], 70)

    def test_files_created_and_edited_distinct_paths(self):
        """files_created and files_edited should count distinct file paths."""
        ts = '2026-02-02T12:00:00'
        self._insert_session('s1', ts)
        self._insert_turn('s1', 'u1', 'assistant', ts)
        # Two Writes to the same file should count as 1 file_created
        self._insert_tool_call('s1', 1, 'Write', ts, file_path='/same.py')
        self.conn.execute("""
            INSERT INTO tool_calls (session_id, turn_id, tool_name, timestamp,
                success, file_path, loc_written, lines_added, lines_deleted)
            VALUES ('s1', 1, 'Write', ?, 1, '/same.py', 0, 0, 0)
        """, (ts,))
        # Two Edits to different files should count as 2 files_edited
        self._insert_tool_call('s1', 1, 'Edit', ts, file_path='/a.py')
        self.conn.execute("""
            INSERT INTO tool_calls (session_id, turn_id, tool_name, timestamp,
                success, file_path, loc_written, lines_added, lines_deleted)
            VALUES ('s1', 1, 'Edit', ?, 1, '/b.py', 0, 0, 0)
        """, (ts,))
        self.conn.commit()

        materialize_daily_summaries(self.conn)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT files_created, files_edited FROM daily_summaries WHERE date = '2026-02-02'"
        ).fetchone()
        self.assertEqual(row[0], 1)  # distinct Write paths: /same.py
        self.assertEqual(row[1], 2)  # distinct Edit paths: /a.py, /b.py

    def test_all_errors_error_rate_is_one(self):
        """error_rate should be 1.0 when all tool_calls are errors."""
        ts = '2026-02-03T12:00:00'
        self._insert_session('s1', ts)
        self._insert_turn('s1', 'u1', 'assistant', ts)
        self._insert_tool_call('s1', 1, 'Bash', ts, success=0)
        self._insert_tool_call('s1', 1, 'Bash', ts, success=0)
        self.conn.commit()

        materialize_daily_summaries(self.conn)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT errors, error_rate FROM daily_summaries WHERE date = '2026-02-03'"
        ).fetchone()
        self.assertEqual(row[0], 2)
        self.assertAlmostEqual(row[1], 1.0)


class TestUserPromptPreviewExtraction(unittest.TestCase):
    """Test user_prompt_preview extraction in the extractor."""

    def _make_entry(self, entry_type='user', content=None, uuid='test-uuid',
                    timestamp='2026-01-15T10:00:00Z'):
        """Build a minimal JSONL entry dict."""
        entry = {
            'uuid': uuid,
            'timestamp': timestamp,
            'type': entry_type,
            'message': {},
        }
        if content is not None:
            entry['message']['content'] = content
        return entry

    def test_text_block_content(self):
        """Extract preview from a list with a single text block."""
        entry = self._make_entry(content=[
            {'type': 'text', 'text': 'Hello, please help me.'}
        ])
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(turn.user_prompt_preview, 'Hello, please help me.')

    def test_plain_string_in_list(self):
        """Extract preview from a list with a plain string element."""
        entry = self._make_entry(content=['Fix the bug in main.py'])
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(turn.user_prompt_preview, 'Fix the bug in main.py')

    def test_string_content_not_list(self):
        """Extract preview when content is a plain string (not a list)."""
        entry = self._make_entry(content='Refactor the module')
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(turn.user_prompt_preview, 'Refactor the module')

    def test_multiple_text_blocks_joined(self):
        """Multiple text blocks should be joined with spaces."""
        entry = self._make_entry(content=[
            {'type': 'text', 'text': 'First part.'},
            {'type': 'text', 'text': 'Second part.'},
        ])
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(turn.user_prompt_preview, 'First part. Second part.')

    def test_mixed_block_types_only_text_extracted(self):
        """Non-text blocks (e.g., tool_result) should be ignored for preview."""
        entry = self._make_entry(content=[
            {'type': 'text', 'text': 'User message'},
            {'type': 'tool_result', 'tool_use_id': 'abc', 'content': 'tool output'},
            {'type': 'image', 'source': {'data': 'base64stuff'}},
        ])
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(turn.user_prompt_preview, 'User message')

    def test_truncation_at_500_chars(self):
        """Preview should be truncated to 500 characters."""
        long_text = 'A' * 1000
        entry = self._make_entry(content=[{'type': 'text', 'text': long_text}])
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(len(turn.user_prompt_preview), 500)
        self.assertEqual(turn.user_prompt_preview, 'A' * 500)

    def test_truncation_at_500_chars_string_content(self):
        """String content should also be truncated to 500 characters."""
        long_text = 'B' * 700
        entry = self._make_entry(content=long_text)
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(len(turn.user_prompt_preview), 500)

    def test_exactly_500_chars_not_truncated(self):
        """Content of exactly 500 chars should be preserved fully."""
        exact_text = 'C' * 500
        entry = self._make_entry(content=exact_text)
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(len(turn.user_prompt_preview), 500)
        self.assertEqual(turn.user_prompt_preview, exact_text)

    def test_assistant_entry_has_no_preview(self):
        """Assistant entries should have user_prompt_preview = None."""
        entry = self._make_entry(
            entry_type='assistant',
            content=[{'type': 'text', 'text': 'I can help you.'}]
        )
        turn = extract_turn_data(entry, 'session-1')
        self.assertIsNone(turn.user_prompt_preview)

    def test_queue_operation_entry_has_no_preview(self):
        """Non-user entry types should have user_prompt_preview = None."""
        entry = self._make_entry(
            entry_type='queue-operation',
            content=[{'type': 'text', 'text': 'queue data'}]
        )
        turn = extract_turn_data(entry, 'session-1')
        self.assertIsNone(turn.user_prompt_preview)

    def test_empty_content_list(self):
        """Empty content list should result in None preview."""
        entry = self._make_entry(content=[])
        turn = extract_turn_data(entry, 'session-1')
        self.assertIsNone(turn.user_prompt_preview)

    def test_no_content_key(self):
        """Missing content key should result in None preview."""
        entry = self._make_entry()  # no content passed
        turn = extract_turn_data(entry, 'session-1')
        self.assertIsNone(turn.user_prompt_preview)

    def test_empty_text_blocks(self):
        """Text blocks with empty strings should produce empty string preview, not None."""
        entry = self._make_entry(content=[
            {'type': 'text', 'text': ''},
        ])
        turn = extract_turn_data(entry, 'session-1')
        # ' '.join(['']) = '', which is falsy, but the code checks `if text_parts:`
        # which is true because there IS an element, so preview = ''
        self.assertEqual(turn.user_prompt_preview, '')

    def test_content_with_only_non_text_blocks(self):
        """Content with only non-text blocks should result in None."""
        entry = self._make_entry(content=[
            {'type': 'tool_result', 'tool_use_id': 'x', 'content': 'output'},
        ])
        turn = extract_turn_data(entry, 'session-1')
        self.assertIsNone(turn.user_prompt_preview)

    def test_mixed_string_and_text_blocks(self):
        """Content with both plain strings and text blocks should join all."""
        entry = self._make_entry(content=[
            'Plain string part',
            {'type': 'text', 'text': 'Text block part'},
        ])
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(turn.user_prompt_preview, 'Plain string part Text block part')

    def test_empty_string_content(self):
        """Empty string content should produce empty string preview."""
        entry = self._make_entry(content='')
        turn = extract_turn_data(entry, 'session-1')
        self.assertEqual(turn.user_prompt_preview, '')


class TestUserPromptPreviewRoundTrip(unittest.TestCase):
    """Test user_prompt_preview survives database insert and retrieval."""

    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / 'test_roundtrip.db'
        self.conn = get_connection(self.db_path)
        ensure_database(self.conn)
        self.config = load_config()

        self.conn.execute("""
            INSERT INTO sessions (session_id, project_path, first_timestamp, file_path)
            VALUES ('s1', '/proj', '2026-01-15T10:00:00', '/f.jsonl')
        """)
        self.conn.commit()

    def tearDown(self):
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_preview_stored_and_retrieved(self):
        """user_prompt_preview should round-trip through the database."""
        turn = TurnData(
            uuid='rt-uuid-1',
            session_id='s1',
            timestamp=datetime(2026, 1, 15, 10, 0, 0),
            entry_type='user',
            usage=TokenUsage(input_tokens=10),
            user_prompt_preview='Fix the login bug',
        )
        upsert_turns_batch(self.conn, [turn], self.config)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT user_prompt_preview FROM turns WHERE uuid = ?", ('rt-uuid-1',)
        ).fetchone()
        self.assertEqual(row[0], 'Fix the login bug')

    def test_null_preview_stored(self):
        """None preview should be stored as NULL."""
        turn = TurnData(
            uuid='rt-uuid-2',
            session_id='s1',
            timestamp=datetime(2026, 1, 15, 10, 1, 0),
            entry_type='assistant',
            usage=TokenUsage(output_tokens=100),
            user_prompt_preview=None,
        )
        upsert_turns_batch(self.conn, [turn], self.config)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT user_prompt_preview FROM turns WHERE uuid = ?", ('rt-uuid-2',)
        ).fetchone()
        self.assertIsNone(row[0])

    def test_long_preview_stored(self):
        """A 500-character preview should survive storage."""
        long_preview = 'X' * 500
        turn = TurnData(
            uuid='rt-uuid-3',
            session_id='s1',
            timestamp=datetime(2026, 1, 15, 10, 2, 0),
            entry_type='user',
            usage=TokenUsage(input_tokens=10),
            user_prompt_preview=long_preview,
        )
        upsert_turns_batch(self.conn, [turn], self.config)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT user_prompt_preview FROM turns WHERE uuid = ?", ('rt-uuid-3',)
        ).fetchone()
        self.assertEqual(len(row[0]), 500)
        self.assertEqual(row[0], long_preview)

    def test_unicode_preview_stored(self):
        """Unicode characters in preview should survive storage."""
        unicode_preview = 'Fix the \u2603 snowman bug \u2764 \u00e9\u00e8\u00ea'
        turn = TurnData(
            uuid='rt-uuid-4',
            session_id='s1',
            timestamp=datetime(2026, 1, 15, 10, 3, 0),
            entry_type='user',
            usage=TokenUsage(input_tokens=10),
            user_prompt_preview=unicode_preview,
        )
        upsert_turns_batch(self.conn, [turn], self.config)
        self.conn.commit()

        row = self.conn.execute(
            "SELECT user_prompt_preview FROM turns WHERE uuid = ?", ('rt-uuid-4',)
        ).fetchone()
        self.assertEqual(row[0], unicode_preview)


class TestSchemaV3Migration(unittest.TestCase):
    """Test schema migration v2 -> v3 (user_prompt_preview)."""

    def test_user_prompt_preview_column_exists(self):
        """After ensure_database, turns should have user_prompt_preview column."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'test_migration.db'
        conn = get_connection(db_path)
        ensure_database(conn)

        cursor = conn.execute("PRAGMA table_info(turns)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn('user_prompt_preview', columns)

        conn.close()
        db_path.unlink()

    def test_migration_from_v2_adds_column(self):
        """Starting from a v2 database, migration should add user_prompt_preview."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'test_v2.db'
        conn = get_connection(db_path)

        # Manually create v2 schema (initial + v1->v2 migration)
        _create_initial_schema(conn)
        set_schema_version(conn, 1)
        conn.commit()
        _migrate_v1_to_v2(conn)
        set_schema_version(conn, 2)
        conn.commit()

        # Verify at v2 and no user_prompt_preview
        self.assertEqual(get_schema_version(conn), 2)
        cursor = conn.execute("PRAGMA table_info(turns)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertNotIn('user_prompt_preview', columns)

        # Insert a turn without user_prompt_preview (v2 schema)
        conn.execute("""
            INSERT INTO sessions (session_id, project_path, first_timestamp, file_path)
            VALUES ('s1', '/p', '2026-01-01T00:00:00', '/f.jsonl')
        """)
        conn.execute("""
            INSERT INTO turns (session_id, uuid, entry_type, timestamp)
            VALUES ('s1', 'u1', 'user', '2026-01-01T00:00:00')
        """)
        conn.commit()

        # Now run the v2->v3 migration
        _migrate_v2_to_v3(conn)
        set_schema_version(conn, 3)
        conn.commit()

        self.assertEqual(get_schema_version(conn), 3)
        cursor = conn.execute("PRAGMA table_info(turns)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn('user_prompt_preview', columns)

        # Existing turn should have NULL for the new column
        row = conn.execute(
            "SELECT user_prompt_preview FROM turns WHERE uuid = 'u1'"
        ).fetchone()
        self.assertIsNone(row[0])

        conn.close()
        db_path.unlink()

    def test_migration_v2_to_v3_rerun_safe(self):
        """Running _migrate_v2_to_v3 twice should not raise an error."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'test_rerun.db'
        conn = get_connection(db_path)
        ensure_database(conn)

        # Column already exists at v3; running migration again should be safe
        _migrate_v2_to_v3(conn)  # should not raise
        conn.commit()

        cursor = conn.execute("PRAGMA table_info(turns)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn('user_prompt_preview', columns)

        conn.close()
        db_path.unlink()

    def test_schema_version_is_4(self):
        """After ensure_database, schema version should be 4."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'test_version.db'
        conn = get_connection(db_path)
        ensure_database(conn)

        self.assertEqual(get_schema_version(conn), 4)
        self.assertEqual(CURRENT_SCHEMA_VERSION, 4)

        conn.close()
        db_path.unlink()

    def test_full_migration_from_v0(self):
        """Starting from scratch (v0), ensure_database should reach v4."""
        temp_dir = tempfile.mkdtemp()
        db_path = Path(temp_dir) / 'test_full.db'
        conn = get_connection(db_path)

        self.assertEqual(get_schema_version(conn), 0)
        ensure_database(conn)
        self.assertEqual(get_schema_version(conn), 4)

        # Verify all tables and the new column exist
        cursor = conn.execute("PRAGMA table_info(turns)")
        columns = [row[1] for row in cursor.fetchall()]
        self.assertIn('user_prompt_preview', columns)

        conn.close()
        db_path.unlink()


if __name__ == '__main__':
    unittest.main()
