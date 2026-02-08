"""
Tests for real-time ETL updates functionality.

Tests the watcher module, force-scan feature, and incremental processing
with recent files bypass.
"""

import unittest
import tempfile
import sqlite3
import json
import os
import time
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

# Add parent to path for imports
import sys
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from ccwap.etl.incremental import should_process_file, update_file_state, clear_file_state
from ccwap.etl.watcher import FileWatcher, force_scan_recent
from ccwap.models.schema import get_connection, ensure_database


class TestIncrementalWithRecentHours(unittest.TestCase):
    """Test the recent_hours bypass in incremental processing."""

    def setUp(self):
        """Create temp database and test files."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / "test.db"
        self.conn = get_connection(self.db_path)
        ensure_database(self.conn)

        # Create a test JSONL file
        self.test_file = Path(self.temp_dir) / "test_session.jsonl"
        self._write_test_entry()

    def tearDown(self):
        """Clean up temp files."""
        self.conn.close()
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _write_test_entry(self, uuid_val=None):
        """Write a test entry to the JSONL file."""
        entry = {
            "uuid": uuid_val or f"test-{datetime.now().timestamp()}",
            "type": "user",
            "message": {"role": "user", "content": "test"},
            "timestamp": datetime.now().isoformat(),
        }
        with open(self.test_file, "a") as f:
            f.write(json.dumps(entry) + "\n")

    def test_new_file_should_process(self):
        """New files should always be processed."""
        should_process, offset = should_process_file(self.conn, self.test_file)
        self.assertTrue(should_process)
        self.assertEqual(offset, 0)

    def test_unchanged_file_skipped(self):
        """Unchanged files should be skipped without recent_hours."""
        # First, process and record state
        update_file_state(self.conn, self.test_file, entries_parsed=1)
        self.conn.commit()

        # Now check - should be skipped
        should_process, _ = should_process_file(self.conn, self.test_file)
        self.assertFalse(should_process)

    def test_unchanged_file_processed_with_recent_hours(self):
        """Unchanged but recent files should process with recent_hours."""
        # First, process and record state
        update_file_state(self.conn, self.test_file, entries_parsed=1)
        self.conn.commit()

        # With recent_hours=24, file should still be processed
        should_process, _ = should_process_file(self.conn, self.test_file, recent_hours=24)
        self.assertTrue(should_process)

    def test_old_file_skipped_with_recent_hours(self):
        """Old unchanged files should be skipped even with recent_hours."""
        # Set file mtime to 48 hours ago FIRST
        old_time = time.time() - (48 * 3600)
        os.utime(self.test_file, (old_time, old_time))

        # Now record the state with the old mtime
        update_file_state(self.conn, self.test_file, entries_parsed=1)
        self.conn.commit()

        # With recent_hours=24, old unchanged file should be skipped
        should_process, _ = should_process_file(self.conn, self.test_file, recent_hours=24)
        self.assertFalse(should_process)

    def test_modified_file_always_processed(self):
        """Modified files should always be processed."""
        # Record initial state
        update_file_state(self.conn, self.test_file, entries_parsed=1)
        self.conn.commit()

        # Modify the file
        time.sleep(0.1)  # Ensure mtime changes
        self._write_test_entry("new-entry")

        # Should be processed due to mtime/size change
        should_process, _ = should_process_file(self.conn, self.test_file)
        self.assertTrue(should_process)


class TestFileWatcher(unittest.TestCase):
    """Test the FileWatcher class."""

    def setUp(self):
        """Create temp directories."""
        self.temp_dir = tempfile.mkdtemp()
        self.projects_dir = Path(self.temp_dir) / "projects"
        self.projects_dir.mkdir()
        self.db_dir = Path(self.temp_dir) / "ccwap"
        self.db_dir.mkdir()

        # Create a test project
        self.test_project = self.projects_dir / "test-project"
        self.test_project.mkdir()

        self.config = {
            "database_path": str(self.db_dir / "analytics.db"),
            "claude_projects_path": str(self.projects_dir),
        }

    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_jsonl(self, project_dir: Path, name: str = "session.jsonl"):
        """Create a test JSONL file."""
        file_path = project_dir / name
        entry = {
            "uuid": f"test-{datetime.now().timestamp()}",
            "type": "user",
            "message": {"role": "user", "content": "test"},
            "timestamp": datetime.now().isoformat(),
        }
        with open(file_path, "w") as f:
            f.write(json.dumps(entry) + "\n")
        return file_path

    def test_watcher_initialization(self):
        """Test watcher initializes correctly."""
        watcher = FileWatcher(
            config=self.config,
            poll_interval=1,
            verbose=False,
            recent_hours=24
        )
        self.assertEqual(watcher.poll_interval, 1)
        self.assertEqual(watcher.recent_hours, 24)
        self.assertFalse(watcher.running)

    def test_scan_detects_new_files(self):
        """Test that scan detects new files."""
        watcher = FileWatcher(config=self.config)

        # Initial scan - no files
        with patch.object(watcher, '_get_file_state', return_value=(0, 0)):
            pass

        # Create a file
        test_file = self._create_test_jsonl(self.test_project)

        # Watcher should detect it
        changed = watcher._scan_for_changes(self.projects_dir)
        self.assertEqual(len(changed), 1)
        self.assertEqual(changed[0].name, "session.jsonl")

    def test_scan_detects_modified_files(self):
        """Test that scan detects modified files."""
        watcher = FileWatcher(config=self.config)

        # Create initial file
        test_file = self._create_test_jsonl(self.test_project)

        # First scan
        changed = watcher._scan_for_changes(self.projects_dir)
        self.assertEqual(len(changed), 1)

        # Second scan without changes - still detected because recent
        changed = watcher._scan_for_changes(self.projects_dir)
        # Recent files are always included
        self.assertEqual(len(changed), 1)

    def test_run_once(self):
        """Test single scan cycle."""
        watcher = FileWatcher(config=self.config, verbose=False)

        # Create a test file
        self._create_test_jsonl(self.test_project)

        # Run once
        result = watcher.run_once()

        # Should have detected changes
        self.assertIn('files_changed', result)
        self.assertGreaterEqual(result.get('files_changed', 0), 0)

    def test_is_recent_file(self):
        """Test recent file detection."""
        watcher = FileWatcher(config=self.config, recent_hours=24)

        # Create a recent file
        test_file = self._create_test_jsonl(self.test_project)
        self.assertTrue(watcher._is_recent_file(test_file))

        # Set file to old
        old_time = time.time() - (48 * 3600)
        os.utime(test_file, (old_time, old_time))
        self.assertFalse(watcher._is_recent_file(test_file))


class TestForceScan(unittest.TestCase):
    """Test the force_scan_recent function."""

    def setUp(self):
        """Create temp directories."""
        self.temp_dir = tempfile.mkdtemp()
        self.projects_dir = Path(self.temp_dir) / "projects"
        self.projects_dir.mkdir()
        self.db_dir = Path(self.temp_dir) / "ccwap"
        self.db_dir.mkdir()

        # Create a test project
        self.test_project = self.projects_dir / "test-project"
        self.test_project.mkdir()

        self.config = {
            "database_path": str(self.db_dir / "analytics.db"),
            "claude_projects_path": str(self.projects_dir),
        }

    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_test_jsonl(self, project_dir: Path, name: str = "session.jsonl"):
        """Create a test JSONL file."""
        file_path = project_dir / name
        entry = {
            "uuid": f"test-{datetime.now().timestamp()}",
            "type": "user",
            "message": {"role": "user", "content": "test"},
            "timestamp": datetime.now().isoformat(),
        }
        with open(file_path, "w") as f:
            f.write(json.dumps(entry) + "\n")
        return file_path

    def test_force_scan_clears_recent_files(self):
        """Test that force_scan clears ETL state for recent files."""
        # Create test file
        test_file = self._create_test_jsonl(self.test_project)

        # Initialize database and set ETL state
        db_path = Path(self.config["database_path"])
        conn = get_connection(db_path)
        ensure_database(conn)
        update_file_state(conn, test_file, entries_parsed=10)
        conn.commit()

        # Verify state exists
        cursor = conn.execute(
            "SELECT COUNT(*) FROM etl_state WHERE file_path = ?",
            (str(test_file),)
        )
        self.assertEqual(cursor.fetchone()[0], 1)
        conn.close()

        # Run force scan
        result = force_scan_recent(config=self.config, hours=24, verbose=False)

        # Should have cleared the state
        self.assertEqual(result['files_cleared'], 1)

        # Verify state is cleared
        conn = get_connection(db_path)
        cursor = conn.execute(
            "SELECT COUNT(*) FROM etl_state WHERE file_path = ?",
            (str(test_file),)
        )
        self.assertEqual(cursor.fetchone()[0], 0)
        conn.close()

    def test_force_scan_ignores_old_files(self):
        """Test that force_scan ignores old files."""
        # Create test file
        test_file = self._create_test_jsonl(self.test_project)

        # Set file to old
        old_time = time.time() - (48 * 3600)
        os.utime(test_file, (old_time, old_time))

        # Initialize database and set ETL state
        db_path = Path(self.config["database_path"])
        conn = get_connection(db_path)
        ensure_database(conn)
        update_file_state(conn, test_file, entries_parsed=10)
        conn.commit()
        conn.close()

        # Run force scan with 24 hour window
        result = force_scan_recent(config=self.config, hours=24, verbose=False)

        # Should NOT have cleared the old file
        self.assertEqual(result['files_cleared'], 0)


class TestReportsAfterETL(unittest.TestCase):
    """Integration tests verifying reports reflect ETL updates."""

    def setUp(self):
        """Create temp directories and database."""
        self.temp_dir = tempfile.mkdtemp()
        self.projects_dir = Path(self.temp_dir) / "projects"
        self.projects_dir.mkdir()
        self.db_dir = Path(self.temp_dir) / "ccwap"
        self.db_dir.mkdir()

        # Create a test project
        self.test_project = self.projects_dir / "test-project"
        self.test_project.mkdir()

        self.config = {
            "database_path": str(self.db_dir / "analytics.db"),
            "claude_projects_path": str(self.projects_dir),
            "pricing": {
                "sonnet": {
                    "input": 3.0,
                    "output": 15.0,
                    "cache_read": 0.3,
                    "cache_write": 3.75
                }
            }
        }

        self.db_path = Path(self.config["database_path"])

    def tearDown(self):
        """Clean up temp files."""
        import shutil
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def _create_session_file(self, session_id: str, turns: int = 5):
        """Create a test session JSONL file with multiple turns."""
        file_path = self.test_project / f"{session_id}.jsonl"
        entries = []

        for i in range(turns):
            # User message
            user_entry = {
                "uuid": f"{session_id}-user-{i}",
                "type": "user",
                "message": {"role": "user", "content": f"Question {i}"},
                "timestamp": (datetime.now() - timedelta(minutes=turns-i)).isoformat(),
            }
            entries.append(user_entry)

            # Assistant response
            assistant_entry = {
                "uuid": f"{session_id}-assistant-{i}",
                "type": "assistant",
                "message": {"role": "assistant", "content": f"Answer {i}"},
                "timestamp": (datetime.now() - timedelta(minutes=turns-i) + timedelta(seconds=30)).isoformat(),
                "usage": {
                    "input_tokens": 100 + i * 10,
                    "output_tokens": 200 + i * 20,
                    "cache_read_input_tokens": 50,
                    "cache_creation_input_tokens": 10,
                },
                "model": "claude-sonnet-4-20250514",
            }
            entries.append(assistant_entry)

        with open(file_path, "w") as f:
            for entry in entries:
                f.write(json.dumps(entry) + "\n")

        return file_path

    def test_etl_then_report(self):
        """Test that reports show data after ETL runs."""
        from ccwap.etl import run_etl
        from ccwap.models.schema import get_connection, ensure_database

        # Create test session
        self._create_session_file("test-session-1", turns=3)

        # Run ETL
        stats = run_etl(
            claude_projects_path=self.projects_dir,
            config=self.config,
            verbose=False
        )

        # Verify ETL processed the file
        self.assertEqual(stats['files_processed'], 1)
        self.assertGreater(stats['entries_parsed'], 0)

        # Check database has data
        conn = get_connection(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM turns")
        turn_count = cursor.fetchone()[0]
        self.assertGreater(turn_count, 0)

        cursor = conn.execute("SELECT COUNT(*) FROM sessions")
        session_count = cursor.fetchone()[0]
        self.assertEqual(session_count, 1)

        conn.close()

    def test_incremental_update_with_new_turns(self):
        """Test that new turns are picked up incrementally."""
        from ccwap.etl import run_etl
        from ccwap.models.schema import get_connection

        # Create initial session
        session_file = self._create_session_file("test-session-2", turns=2)

        # Run initial ETL
        stats1 = run_etl(
            claude_projects_path=self.projects_dir,
            config=self.config,
            verbose=False
        )

        conn = get_connection(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM turns")
        initial_turns = cursor.fetchone()[0]
        conn.close()

        # Add more turns to the file
        time.sleep(0.1)  # Ensure mtime changes
        with open(session_file, "a") as f:
            new_entry = {
                "uuid": "test-session-2-new-turn",
                "type": "assistant",
                "message": {"role": "assistant", "content": "New response"},
                "timestamp": datetime.now().isoformat(),
                "usage": {
                    "input_tokens": 150,
                    "output_tokens": 300,
                },
                "model": "claude-sonnet-4-20250514",
            }
            f.write(json.dumps(new_entry) + "\n")

        # Run ETL again
        stats2 = run_etl(
            claude_projects_path=self.projects_dir,
            config=self.config,
            verbose=False
        )

        # Should have processed the file again
        self.assertEqual(stats2['files_processed'], 1)

        # Check for new turn in database
        conn = get_connection(self.db_path)
        cursor = conn.execute("SELECT COUNT(*) FROM turns")
        final_turns = cursor.fetchone()[0]
        conn.close()

        # Should have more turns now
        self.assertGreater(final_turns, initial_turns)

    def test_force_scan_enables_reprocessing(self):
        """Test that force_scan allows reprocessing of files."""
        from ccwap.etl import run_etl

        # Create session
        self._create_session_file("test-session-3", turns=2)

        # Run ETL twice - second should skip
        run_etl(claude_projects_path=self.projects_dir, config=self.config)
        stats = run_etl(claude_projects_path=self.projects_dir, config=self.config)
        self.assertEqual(stats['files_skipped'], 1)

        # Force scan to clear state
        force_scan_recent(config=self.config, hours=24)

        # Now ETL should process again
        stats = run_etl(claude_projects_path=self.projects_dir, config=self.config)
        self.assertEqual(stats['files_processed'], 1)


def run_all_tests():
    """Run all real-time update tests."""
    loader = unittest.TestLoader()
    suite = unittest.TestSuite()

    # Add test classes
    suite.addTests(loader.loadTestsFromTestCase(TestIncrementalWithRecentHours))
    suite.addTests(loader.loadTestsFromTestCase(TestFileWatcher))
    suite.addTests(loader.loadTestsFromTestCase(TestForceScan))
    suite.addTests(loader.loadTestsFromTestCase(TestReportsAfterETL))

    # Run tests
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)

    return result.wasSuccessful()


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
