"""Tests for advanced features (Phase 8)."""

import unittest
import sqlite3
import tempfile
import json
from pathlib import Path
from datetime import datetime, timedelta

from ccwap.models.schema import ensure_database, get_connection


class AdvancedTestBase(unittest.TestCase):
    """Base class with test database setup."""

    def setUp(self):
        """Create test database with sample data."""
        self.temp_dir = tempfile.mkdtemp()
        self.db_path = Path(self.temp_dir) / 'test.db'
        self.conn = get_connection(self.db_path)
        ensure_database(self.conn)
        self._populate_test_data()

    def tearDown(self):
        """Clean up."""
        self.conn.close()
        if self.db_path.exists():
            self.db_path.unlink()

    def _populate_test_data(self):
        """Insert sample data spanning multiple weeks."""
        now = datetime.now()

        # Insert sessions across multiple weeks
        for i in range(4):
            week_offset = timedelta(weeks=i)
            timestamp = (now - week_offset).isoformat()

            self.conn.execute("""
                INSERT INTO sessions (session_id, project_path, project_display,
                    first_timestamp, last_timestamp, duration_seconds, file_path)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (f'sess-week-{i}', '/path/proj', 'TestProject',
                  timestamp, timestamp, 3600, f'/logs/sess-{i}.jsonl'))

            # Insert turns
            self.conn.execute("""
                INSERT INTO turns (session_id, uuid, entry_type, timestamp,
                    model, input_tokens, output_tokens, cache_read_tokens, cost)
                VALUES (?, ?, 'user', ?, 'claude-opus-4-5-20251101', ?, ?, ?, ?)
            """, (f'sess-week-{i}', f'uuid-{i}', timestamp,
                  100 + i*10, 500 + i*50, 50, 0.05 + i*0.01))

            # Insert tool calls
            self.conn.execute("""
                INSERT INTO tool_calls (session_id, turn_id, tool_name, timestamp,
                    success, loc_written)
                VALUES (?, 1, 'Write', ?, 1, ?)
            """, (f'sess-week-{i}', timestamp, 50 + i*10))

        self.conn.commit()


class TestForecastReport(AdvancedTestBase):
    """Test forecast report generation."""

    def test_generate_forecast(self):
        """Verify forecast report generates."""
        from ccwap.reports.forecast import generate_forecast

        result = generate_forecast(self.conn, {}, color_enabled=False)

        # May not have enough data for full forecast
        self.assertIn('SPEND FORECAST', result)


class TestCompareReport(AdvancedTestBase):
    """Test comparison report generation."""

    def test_parse_last_week(self):
        """Verify last-week period parsing."""
        from ccwap.reports.compare import parse_compare_period

        current_from, current_to, prev_from, prev_to = parse_compare_period('last-week')

        # Current should start on Monday
        self.assertEqual(current_from.weekday(), 0)
        # Previous should be the week before
        self.assertEqual(prev_from.weekday(), 0)

    def test_parse_custom_range(self):
        """Verify custom date range parsing."""
        from ccwap.reports.compare import parse_compare_period

        current_from, current_to, prev_from, prev_to = parse_compare_period('2024-01-15..2024-01-21')

        self.assertEqual(current_from.month, 1)
        self.assertEqual(current_from.day, 15)
        self.assertEqual(current_to.day, 21)

    def test_generate_compare(self):
        """Verify comparison report generates."""
        from ccwap.reports.compare import generate_compare

        result = generate_compare(self.conn, 'last-week', {}, color_enabled=False)

        self.assertIn('PERIOD COMPARISON', result)
        self.assertIn('Current', result)
        self.assertIn('Previous', result)

    def test_compare_by_project(self):
        """Verify comparison with project breakdown."""
        from ccwap.reports.compare import generate_compare

        result = generate_compare(self.conn, 'last-week', {},
                                 by_project=True, color_enabled=False)

        self.assertIn('BY PROJECT', result)


class TestTrendReport(AdvancedTestBase):
    """Test trend report generation."""

    def test_parse_period_weeks(self):
        """Verify week period parsing."""
        from ccwap.reports.trend import parse_period

        self.assertEqual(parse_period('4w'), 4)
        self.assertEqual(parse_period('8w'), 8)
        self.assertEqual(parse_period('12w'), 12)

    def test_generate_trend_cost(self):
        """Verify cost trend report."""
        from ccwap.reports.trend import generate_trend

        result = generate_trend(self.conn, 'cost', {}, period='4w', color_enabled=False)

        self.assertIn('TREND', result)
        self.assertIn('COST', result)

    def test_generate_trend_tokens(self):
        """Verify token trend report."""
        from ccwap.reports.trend import generate_trend

        result = generate_trend(self.conn, 'tokens', {}, period='4w', color_enabled=False)

        self.assertIn('TREND', result)
        self.assertIn('TOKENS', result)

    def test_generate_trend_sessions(self):
        """Verify sessions trend report."""
        from ccwap.reports.trend import generate_trend

        result = generate_trend(self.conn, 'sessions', {}, period='4w', color_enabled=False)

        self.assertIn('TREND', result)
        self.assertIn('SESSIONS', result)


class TestExperimentTags(AdvancedTestBase):
    """Test experiment tagging functionality."""

    def test_tag_sessions(self):
        """Verify session tagging."""
        from ccwap.reports.tags import tag_sessions

        count = tag_sessions(self.conn, 'test-tag', session_ids=['sess-week-0', 'sess-week-1'])

        self.assertEqual(count, 2)

        # Verify tags were created
        cursor = self.conn.execute("""
            SELECT COUNT(*) FROM experiment_tags WHERE tag_name = 'test-tag'
        """)
        self.assertEqual(cursor.fetchone()[0], 2)

    def test_tag_sessions_by_date(self):
        """Verify tagging by date range."""
        from ccwap.reports.tags import tag_sessions

        now = datetime.now()
        count = tag_sessions(self.conn, 'recent-tag',
                            date_from=now - timedelta(days=7),
                            date_to=now)

        self.assertGreater(count, 0)

    def test_list_tags(self):
        """Verify tag listing."""
        from ccwap.reports.tags import tag_sessions, list_tags

        # Create some tags
        tag_sessions(self.conn, 'tag-a', session_ids=['sess-week-0'])
        tag_sessions(self.conn, 'tag-b', session_ids=['sess-week-1', 'sess-week-2'])

        result = list_tags(self.conn, color_enabled=False)

        self.assertIn('EXPERIMENT TAGS', result)
        self.assertIn('tag-a', result)
        self.assertIn('tag-b', result)

    def test_compare_tags(self):
        """Verify tag comparison."""
        from ccwap.reports.tags import tag_sessions, compare_tags

        # Create tags
        tag_sessions(self.conn, 'experiment-a', session_ids=['sess-week-0', 'sess-week-1'])
        tag_sessions(self.conn, 'experiment-b', session_ids=['sess-week-2', 'sess-week-3'])

        result = compare_tags(self.conn, 'experiment-a', 'experiment-b', {}, color_enabled=False)

        self.assertIn('COMPARING', result)
        self.assertIn('experiment-a', result)
        self.assertIn('experiment-b', result)

    def test_compare_tags_not_found(self):
        """Verify handling of missing tags."""
        from ccwap.reports.tags import compare_tags

        result = compare_tags(self.conn, 'nonexistent', 'also-missing', {}, color_enabled=False)

        self.assertIn('not found', result)


class TestSnapshots(AdvancedTestBase):
    """Test snapshot functionality."""

    def test_create_snapshot(self):
        """Verify snapshot creation."""
        from ccwap.output.snapshot import create_snapshot

        snapshot = create_snapshot(self.conn)

        self.assertIn('version', snapshot)
        self.assertIn('created_at', snapshot)
        self.assertIn('totals', snapshot)
        self.assertIn('projects', snapshot)

        # Verify totals
        self.assertGreater(snapshot['totals']['sessions'], 0)
        self.assertGreater(snapshot['totals']['cost'], 0)

    def test_create_snapshot_to_file(self):
        """Verify snapshot saved to file."""
        from ccwap.output.snapshot import create_snapshot

        snapshot_path = Path(self.temp_dir) / 'snapshot.json'
        snapshot = create_snapshot(self.conn, snapshot_path)

        self.assertTrue(snapshot_path.exists())

        # Verify file content
        with open(snapshot_path) as f:
            loaded = json.load(f)

        self.assertEqual(loaded['version'], snapshot['version'])

    def test_load_snapshot(self):
        """Verify snapshot loading."""
        from ccwap.output.snapshot import create_snapshot, load_snapshot

        snapshot_path = Path(self.temp_dir) / 'snapshot.json'
        original = create_snapshot(self.conn, snapshot_path)

        loaded = load_snapshot(snapshot_path)

        self.assertIsNotNone(loaded)
        self.assertEqual(loaded['version'], original['version'])

    def test_load_snapshot_not_found(self):
        """Verify handling of missing snapshot."""
        from ccwap.output.snapshot import load_snapshot

        result = load_snapshot(Path('/nonexistent/path.json'))

        self.assertIsNone(result)

    def test_compare_snapshots(self):
        """Verify snapshot comparison."""
        from ccwap.output.snapshot import create_snapshot, compare_snapshots

        # Create first snapshot
        snapshot1 = create_snapshot(self.conn)

        # Add more data
        self.conn.execute("""
            INSERT INTO sessions (session_id, project_path, project_display,
                first_timestamp, file_path)
            VALUES ('new-sess', '/path/new', 'NewProject', ?, '/logs/new.jsonl')
        """, (datetime.now().isoformat(),))
        self.conn.execute("""
            INSERT INTO turns (session_id, uuid, entry_type, timestamp,
                input_tokens, output_tokens, cost)
            VALUES ('new-sess', 'new-uuid', 'user', ?, 100, 500, 0.10)
        """, (datetime.now().isoformat(),))
        self.conn.commit()

        # Create second snapshot
        snapshot2 = create_snapshot(self.conn)

        # Compare
        result = compare_snapshots(snapshot2, snapshot1, color_enabled=False)

        self.assertIn('SNAPSHOT COMPARISON', result)
        self.assertIn('Previous', result)
        self.assertIn('Current', result)

    def test_generate_diff(self):
        """Verify diff generation from file."""
        from ccwap.output.snapshot import create_snapshot, generate_diff

        # Create snapshot file
        snapshot_path = Path(self.temp_dir) / 'old_snapshot.json'
        create_snapshot(self.conn, snapshot_path)

        # Generate diff
        result = generate_diff(self.conn, str(snapshot_path), {}, color_enabled=False)

        self.assertIn('SNAPSHOT COMPARISON', result)

    def test_generate_diff_file_not_found(self):
        """Verify handling of missing snapshot file."""
        from ccwap.output.snapshot import generate_diff

        result = generate_diff(self.conn, '/nonexistent.json', {}, color_enabled=False)

        self.assertIn('not found', result)


class TestCSVExport(AdvancedTestBase):
    """Test CSV export functionality."""

    def test_export_daily(self):
        """Verify daily export creates CSV."""
        from ccwap.output.csv_export import export_daily

        output_path = Path(self.temp_dir) / 'daily.csv'
        count = export_daily(self.conn, output_path)

        self.assertTrue(output_path.exists())
        self.assertGreater(count, 0)

        # Verify CSV has header
        with open(output_path) as f:
            header = f.readline()
            self.assertIn('date', header)
            self.assertIn('sessions', header)
            self.assertIn('cost', header)

    def test_export_projects(self):
        """Verify projects export creates CSV."""
        from ccwap.output.csv_export import export_projects

        output_path = Path(self.temp_dir) / 'projects.csv'
        count = export_projects(self.conn, output_path)

        self.assertTrue(output_path.exists())
        self.assertGreater(count, 0)

    def test_export_tools(self):
        """Verify tools export creates CSV."""
        from ccwap.output.csv_export import export_tools

        output_path = Path(self.temp_dir) / 'tools.csv'
        count = export_tools(self.conn, output_path)

        self.assertTrue(output_path.exists())
        self.assertGreater(count, 0)

    def test_export_sessions(self):
        """Verify sessions export creates CSV."""
        from ccwap.output.csv_export import export_sessions

        output_path = Path(self.temp_dir) / 'sessions.csv'
        count = export_sessions(self.conn, output_path)

        self.assertTrue(output_path.exists())
        self.assertGreater(count, 0)

    def test_export_summary(self):
        """Verify summary export creates CSV."""
        from ccwap.output.csv_export import export_summary

        output_path = Path(self.temp_dir) / 'summary.csv'
        count = export_summary(self.conn, output_path)

        self.assertTrue(output_path.exists())
        self.assertEqual(count, 2)  # All Time + Today

    def test_export_report_function(self):
        """Verify unified export_report function."""
        from ccwap.output.csv_export import export_report

        output_path = Path(self.temp_dir) / 'report.csv'
        result = export_report(self.conn, str(output_path), 'daily')

        self.assertIn('Exported', result)
        self.assertTrue(output_path.exists())


if __name__ == '__main__':
    unittest.main()
