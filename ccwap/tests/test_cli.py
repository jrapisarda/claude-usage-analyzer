"""Tests for CLI argument parsing and integration."""

import unittest
from datetime import datetime, timedelta

from ccwap.ccwap import create_parser, parse_date_filters


class TestArgumentParser(unittest.TestCase):
    """Test CLI argument parsing."""

    def setUp(self):
        """Create parser."""
        self.parser = create_parser()

    def test_default_no_args(self):
        """Verify default with no arguments."""
        args = self.parser.parse_args([])

        self.assertFalse(args.all)
        self.assertFalse(args.daily)
        self.assertFalse(args.verbose)

    def test_all_flag(self):
        """Verify --all flag."""
        args = self.parser.parse_args(['--all'])
        self.assertTrue(args.all)

    def test_all_short_flag(self):
        """Verify -a short flag."""
        args = self.parser.parse_args(['-a'])
        self.assertTrue(args.all)

    def test_daily_flag(self):
        """Verify --daily flag."""
        args = self.parser.parse_args(['--daily'])
        self.assertTrue(args.daily)

    def test_weekly_flag(self):
        """Verify --weekly flag."""
        args = self.parser.parse_args(['--weekly'])
        self.assertTrue(args.weekly)

    def test_projects_flag(self):
        """Verify --projects flag."""
        args = self.parser.parse_args(['--projects'])
        self.assertTrue(args.projects)

    def test_tools_flag(self):
        """Verify --tools flag."""
        args = self.parser.parse_args(['--tools'])
        self.assertTrue(args.tools)

    def test_languages_flag(self):
        """Verify --languages flag."""
        args = self.parser.parse_args(['--languages'])
        self.assertTrue(args.languages)

    def test_efficiency_flag(self):
        """Verify --efficiency flag."""
        args = self.parser.parse_args(['--efficiency'])
        self.assertTrue(args.efficiency)

    def test_errors_flag(self):
        """Verify --errors flag."""
        args = self.parser.parse_args(['--errors'])
        self.assertTrue(args.errors)

    def test_hourly_flag(self):
        """Verify --hourly flag."""
        args = self.parser.parse_args(['--hourly'])
        self.assertTrue(args.hourly)

    def test_sessions_flag(self):
        """Verify --sessions flag."""
        args = self.parser.parse_args(['--sessions'])
        self.assertTrue(args.sessions)

    def test_forecast_flag(self):
        """Verify --forecast flag."""
        args = self.parser.parse_args(['--forecast'])
        self.assertTrue(args.forecast)

    def test_db_stats_flag(self):
        """Verify --db-stats flag."""
        args = self.parser.parse_args(['--db-stats'])
        self.assertTrue(args.db_stats)

    def test_session_with_id(self):
        """Verify --session takes ID."""
        args = self.parser.parse_args(['--session', 'abc123'])
        self.assertEqual(args.session, 'abc123')

    def test_replay_with_id(self):
        """Verify --replay takes ID."""
        args = self.parser.parse_args(['--replay', 'xyz789'])
        self.assertEqual(args.replay, 'xyz789')

    def test_project_filter(self):
        """Verify --project filter."""
        args = self.parser.parse_args(['--project', 'myproject'])
        self.assertEqual(args.project, 'myproject')

    def test_sort_field(self):
        """Verify --sort field."""
        args = self.parser.parse_args(['--sort', 'cost'])
        self.assertEqual(args.sort, 'cost')

    def test_no_color_flag(self):
        """Verify --no-color flag."""
        args = self.parser.parse_args(['--no-color'])
        self.assertTrue(args.no_color)

    def test_verbose_flag(self):
        """Verify --verbose flag."""
        args = self.parser.parse_args(['--verbose'])
        self.assertTrue(args.verbose)

    def test_verbose_short_flag(self):
        """Verify -v short flag."""
        args = self.parser.parse_args(['-v'])
        self.assertTrue(args.verbose)

    def test_rebuild_flag(self):
        """Verify --rebuild flag."""
        args = self.parser.parse_args(['--rebuild'])
        self.assertTrue(args.rebuild)

    def test_json_output_flag(self):
        """Verify --json flag."""
        args = self.parser.parse_args(['--json'])
        self.assertTrue(args.json)

    def test_export_with_file(self):
        """Verify --export takes filename."""
        args = self.parser.parse_args(['--export', 'output.csv'])
        self.assertEqual(args.export, 'output.csv')


class TestDateFilters(unittest.TestCase):
    """Test date filter parsing."""

    def setUp(self):
        """Create parser."""
        self.parser = create_parser()

    def test_today_filter(self):
        """Verify --today filter."""
        args = self.parser.parse_args(['--today'])
        date_from, date_to = parse_date_filters(args)

        now = datetime.now()
        self.assertEqual(date_from.date(), now.date())
        self.assertEqual(date_to.date(), now.date())

    def test_yesterday_filter(self):
        """Verify --yesterday filter."""
        args = self.parser.parse_args(['--yesterday'])
        date_from, date_to = parse_date_filters(args)

        yesterday = datetime.now() - timedelta(days=1)
        self.assertEqual(date_from.date(), yesterday.date())
        self.assertEqual(date_to.date(), yesterday.date())

    def test_this_week_filter(self):
        """Verify --this-week filter."""
        args = self.parser.parse_args(['--this-week'])
        date_from, date_to = parse_date_filters(args)

        now = datetime.now()
        # Should start on Monday
        self.assertEqual(date_from.weekday(), 0)
        self.assertEqual(date_to.date(), now.date())

    def test_last_week_filter(self):
        """Verify --last-week filter."""
        args = self.parser.parse_args(['--last-week'])
        date_from, date_to = parse_date_filters(args)

        # Should be Monday to Sunday of last week
        self.assertEqual(date_from.weekday(), 0)  # Monday
        self.assertEqual(date_to.weekday(), 6)    # Sunday

    def test_this_month_filter(self):
        """Verify --this-month filter."""
        args = self.parser.parse_args(['--this-month'])
        date_from, date_to = parse_date_filters(args)

        now = datetime.now()
        self.assertEqual(date_from.day, 1)
        self.assertEqual(date_from.month, now.month)
        self.assertEqual(date_to.date(), now.date())

    def test_last_month_filter(self):
        """Verify --last-month filter."""
        args = self.parser.parse_args(['--last-month'])
        date_from, date_to = parse_date_filters(args)

        now = datetime.now()
        # Should be first of previous month
        self.assertEqual(date_from.day, 1)
        if now.month == 1:
            self.assertEqual(date_from.month, 12)
        else:
            self.assertEqual(date_from.month, now.month - 1)

    def test_from_date_filter(self):
        """Verify --from date filter."""
        args = self.parser.parse_args(['--from', '2024-01-15'])
        date_from, date_to = parse_date_filters(args)

        self.assertEqual(date_from.year, 2024)
        self.assertEqual(date_from.month, 1)
        self.assertEqual(date_from.day, 15)
        # date_to defaults to now
        self.assertIsNotNone(date_to)

    def test_from_to_date_filters(self):
        """Verify --from and --to together."""
        args = self.parser.parse_args(['--from', '2024-01-01', '--to', '2024-01-31'])
        date_from, date_to = parse_date_filters(args)

        self.assertEqual(date_from.year, 2024)
        self.assertEqual(date_from.month, 1)
        self.assertEqual(date_from.day, 1)
        self.assertEqual(date_to.year, 2024)
        self.assertEqual(date_to.month, 1)
        self.assertEqual(date_to.day, 31)

    def test_no_date_filter(self):
        """Verify no filter returns None."""
        args = self.parser.parse_args([])
        date_from, date_to = parse_date_filters(args)

        self.assertIsNone(date_from)
        self.assertIsNone(date_to)


class TestMutuallyExclusiveReports(unittest.TestCase):
    """Test that report flags are mutually exclusive."""

    def setUp(self):
        """Create parser."""
        self.parser = create_parser()

    def test_all_and_daily_exclusive(self):
        """Verify --all and --daily are mutually exclusive."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(['--all', '--daily'])

    def test_daily_and_weekly_exclusive(self):
        """Verify --daily and --weekly are mutually exclusive."""
        with self.assertRaises(SystemExit):
            self.parser.parse_args(['--daily', '--weekly'])


class TestAdvancedFeatureFlags(unittest.TestCase):
    """Test Phase 8 advanced feature flags."""

    def setUp(self):
        """Create parser."""
        self.parser = create_parser()

    def test_compare_flag(self):
        """Verify --compare takes period."""
        args = self.parser.parse_args(['--compare', 'last-week'])
        self.assertEqual(args.compare, 'last-week')

    def test_trend_flag(self):
        """Verify --trend takes metric."""
        args = self.parser.parse_args(['--trend', 'cost'])
        self.assertEqual(args.trend, 'cost')

    def test_last_flag(self):
        """Verify --last takes period."""
        args = self.parser.parse_args(['--last', '8w'])
        self.assertEqual(args.last, '8w')

    def test_tag_flag(self):
        """Verify --tag takes name."""
        args = self.parser.parse_args(['--tag', 'experiment-1'])
        self.assertEqual(args.tag, 'experiment-1')

    def test_compare_tags_flag(self):
        """Verify --compare-tags takes two tags."""
        args = self.parser.parse_args(['--compare-tags', 'tag1', 'tag2'])
        self.assertEqual(args.compare_tags, ['tag1', 'tag2'])

    def test_diff_flag(self):
        """Verify --diff takes file."""
        args = self.parser.parse_args(['--diff', 'snapshot.json'])
        self.assertEqual(args.diff, 'snapshot.json')


class TestServeFlags(unittest.TestCase):
    """Test --serve and related flags."""

    def setUp(self):
        """Create parser."""
        self.parser = create_parser()

    def test_serve_flag(self):
        """Verify --serve flag."""
        args = self.parser.parse_args(['--serve'])
        self.assertTrue(args.serve)

    def test_serve_default_port(self):
        """Verify default port is 8080."""
        args = self.parser.parse_args(['--serve'])
        self.assertEqual(args.port, 8080)

    def test_serve_custom_port(self):
        """Verify custom port."""
        args = self.parser.parse_args(['--serve', '--port', '3000'])
        self.assertEqual(args.port, 3000)

    def test_serve_default_host(self):
        """Verify default host is 0.0.0.0."""
        args = self.parser.parse_args(['--serve'])
        self.assertEqual(args.host, '0.0.0.0')

    def test_serve_custom_host(self):
        """Verify custom host."""
        args = self.parser.parse_args(['--serve', '--host', '0.0.0.0'])
        self.assertEqual(args.host, '0.0.0.0')

    def test_serve_no_browser(self):
        """Verify --no-browser flag."""
        args = self.parser.parse_args(['--serve', '--no-browser'])
        self.assertTrue(args.no_browser)

    def test_serve_no_browser_default(self):
        """Verify --no-browser defaults to False."""
        args = self.parser.parse_args(['--serve'])
        self.assertFalse(args.no_browser)


if __name__ == '__main__':
    unittest.main()
