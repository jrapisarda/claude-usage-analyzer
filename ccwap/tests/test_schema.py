"""Tests for database schema creation and migrations."""

import sqlite3
import tempfile
import unittest
from pathlib import Path

from ccwap.models.schema import (
    get_connection,
    ensure_database,
    get_schema_version,
    set_schema_version,
    drop_all_tables,
    CURRENT_SCHEMA_VERSION,
)


class TestSchemaCreation(unittest.TestCase):
    """Test database schema creation."""

    def setUp(self):
        """Create a temporary database for each test."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.conn = get_connection(self.db_path)

    def tearDown(self):
        """Clean up temporary database."""
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_database_created(self):
        """Verify database file is created."""
        self.assertTrue(self.db_path.exists())

    def test_wal_mode_enabled(self):
        """Verify WAL journal mode is enabled."""
        cursor = self.conn.execute("PRAGMA journal_mode")
        mode = cursor.fetchone()[0]
        self.assertEqual(mode.lower(), "wal")

    def test_foreign_keys_enabled(self):
        """Verify foreign keys are enabled."""
        cursor = self.conn.execute("PRAGMA foreign_keys")
        enabled = cursor.fetchone()[0]
        self.assertEqual(enabled, 1)

    def test_all_tables_created(self):
        """Verify all 8 tables are created."""
        ensure_database(self.conn)

        cursor = self.conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
            ORDER BY name
        """)
        tables = [row[0] for row in cursor.fetchall()]

        expected_tables = [
            'daily_summaries',
            'etl_state',
            'experiment_tags',
            'sessions',
            'snapshots',
            'tag_definitions',
            'tool_calls',
            'turns',
        ]
        self.assertEqual(sorted(tables), expected_tables)

    def test_indexes_created(self):
        """Verify required indexes are created."""
        ensure_database(self.conn)

        cursor = self.conn.execute("""
            SELECT name FROM sqlite_master
            WHERE type='index' AND name LIKE 'idx_%'
            ORDER BY name
        """)
        indexes = [row[0] for row in cursor.fetchall()]

        # Check that key indexes exist
        expected_indexes = [
            'idx_sessions_project_path',
            'idx_turns_session_id',
            'idx_turns_timestamp',
            'idx_tool_calls_session_id',
            'idx_tool_calls_tool_name',
            'idx_experiment_tags_tag_name',
        ]
        for idx in expected_indexes:
            self.assertIn(idx, indexes, f"Index {idx} not found")

    def test_schema_version_tracking(self):
        """Verify PRAGMA user_version is set correctly."""
        # Before ensure_database, version should be 0
        self.assertEqual(get_schema_version(self.conn), 0)

        ensure_database(self.conn)

        # After ensure_database, version should match CURRENT_SCHEMA_VERSION
        self.assertEqual(get_schema_version(self.conn), CURRENT_SCHEMA_VERSION)

    def test_migration_is_idempotent(self):
        """Verify running ensure_database twice doesn't break anything."""
        ensure_database(self.conn)
        version1 = get_schema_version(self.conn)

        ensure_database(self.conn)
        version2 = get_schema_version(self.conn)

        self.assertEqual(version1, version2)

        # Verify we still have all tables
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM sqlite_master
            WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        table_count = cursor.fetchone()[0]
        self.assertEqual(table_count, 8)

    def test_uuid_uniqueness_constraint(self):
        """Verify duplicate UUID inserts are rejected."""
        ensure_database(self.conn)

        # Insert a session first
        self.conn.execute("""
            INSERT INTO sessions (session_id, project_path, first_timestamp, file_path)
            VALUES ('test-session', 'test-project', '2026-01-01T00:00:00Z', '/test/path.jsonl')
        """)

        # Insert first turn
        self.conn.execute("""
            INSERT INTO turns (session_id, uuid, timestamp, entry_type)
            VALUES ('test-session', 'unique-uuid-123', '2026-01-01T00:00:00Z', 'user')
        """)
        self.conn.commit()

        # Try to insert duplicate UUID - should raise IntegrityError
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("""
                INSERT INTO turns (session_id, uuid, timestamp, entry_type)
                VALUES ('test-session', 'unique-uuid-123', '2026-01-01T00:01:00Z', 'assistant')
            """)

    def test_insert_or_ignore_for_dedup(self):
        """Verify INSERT OR IGNORE works for deduplication."""
        ensure_database(self.conn)

        # Insert session
        self.conn.execute("""
            INSERT INTO sessions (session_id, project_path, first_timestamp, file_path)
            VALUES ('test-session', 'test-project', '2026-01-01T00:00:00Z', '/test/path.jsonl')
        """)

        # Insert first turn
        self.conn.execute("""
            INSERT INTO turns (session_id, uuid, timestamp, entry_type, cost)
            VALUES ('test-session', 'uuid-1', '2026-01-01T00:00:00Z', 'user', 1.0)
        """)

        # Try INSERT OR IGNORE with same UUID - should be silently ignored
        cursor = self.conn.execute("""
            INSERT OR IGNORE INTO turns (session_id, uuid, timestamp, entry_type, cost)
            VALUES ('test-session', 'uuid-1', '2026-01-01T00:01:00Z', 'assistant', 2.0)
        """)
        self.conn.commit()

        # Verify only one turn exists with original cost
        cursor = self.conn.execute("SELECT COUNT(*), SUM(cost) FROM turns")
        count, total_cost = cursor.fetchone()
        self.assertEqual(count, 1)
        self.assertEqual(total_cost, 1.0)

    def test_drop_all_tables(self):
        """Verify drop_all_tables removes everything."""
        ensure_database(self.conn)

        # Verify tables exist
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        self.assertGreater(cursor.fetchone()[0], 0)

        drop_all_tables(self.conn)

        # Verify tables are gone
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM sqlite_master WHERE type='table' AND name NOT LIKE 'sqlite_%'
        """)
        self.assertEqual(cursor.fetchone()[0], 0)

        # Verify schema version is reset
        self.assertEqual(get_schema_version(self.conn), 0)


class TestSchemaStructure(unittest.TestCase):
    """Test specific schema structure requirements."""

    def setUp(self):
        """Create a temporary database with schema."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.conn = get_connection(self.db_path)
        ensure_database(self.conn)

    def tearDown(self):
        """Clean up."""
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def test_turns_has_pricing_version(self):
        """Verify turns table has pricing_version column."""
        cursor = self.conn.execute("PRAGMA table_info(turns)")
        columns = {row[1] for row in cursor.fetchall()}
        self.assertIn('pricing_version', columns)

    def test_etl_state_has_byte_offset(self):
        """Verify etl_state has last_byte_offset for incremental parsing."""
        cursor = self.conn.execute("PRAGMA table_info(etl_state)")
        columns = {row[1] for row in cursor.fetchall()}
        self.assertIn('last_byte_offset', columns)

    def test_sessions_has_is_agent(self):
        """Verify sessions table has is_agent flag."""
        cursor = self.conn.execute("PRAGMA table_info(sessions)")
        columns = {row[1] for row in cursor.fetchall()}
        self.assertIn('is_agent', columns)

    def test_tool_calls_has_loc_fields(self):
        """Verify tool_calls has LOC tracking fields."""
        cursor = self.conn.execute("PRAGMA table_info(tool_calls)")
        columns = {row[1] for row in cursor.fetchall()}
        self.assertIn('loc_written', columns)
        self.assertIn('lines_added', columns)
        self.assertIn('lines_deleted', columns)

    def test_experiment_tags_unique_constraint(self):
        """Verify experiment_tags has unique constraint on (tag_name, session_id)."""
        # Insert session
        self.conn.execute("""
            INSERT INTO sessions (session_id, project_path, first_timestamp, file_path)
            VALUES ('session-1', 'project', '2026-01-01T00:00:00Z', '/path')
        """)

        # Insert tag
        self.conn.execute("""
            INSERT INTO experiment_tags (tag_name, session_id)
            VALUES ('test-tag', 'session-1')
        """)
        self.conn.commit()

        # Duplicate should fail
        with self.assertRaises(sqlite3.IntegrityError):
            self.conn.execute("""
                INSERT INTO experiment_tags (tag_name, session_id)
                VALUES ('test-tag', 'session-1')
            """)


if __name__ == '__main__':
    unittest.main()
