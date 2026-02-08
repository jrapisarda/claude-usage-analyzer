#!/usr/bin/env python3
"""
Claude Code Workflow Analytics Platform (CCWAP)

A CLI tool for analyzing Claude Code session data.

Usage:
    python -m ccwap [options]
    python ccwap.py [options]
"""

import argparse
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional, Tuple

from ccwap.config.loader import load_config, check_claude_settings, get_database_path
from ccwap.models.schema import get_connection, ensure_database


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser with all CLI flags."""
    parser = argparse.ArgumentParser(
        prog='ccwap',
        description='Claude Code Workflow Analytics Platform'
    )

    # Report views (mutually exclusive group)
    views = parser.add_mutually_exclusive_group()
    views.add_argument('--all', '-a', action='store_true',
                      help='Show all reports')
    views.add_argument('--daily', action='store_true',
                      help='Daily breakdown (rolling 30 days)')
    views.add_argument('--weekly', action='store_true',
                      help='Weekly totals with WoW deltas')
    views.add_argument('--projects', action='store_true',
                      help='Project metrics (30+ fields)')
    views.add_argument('--tools', action='store_true',
                      help='Tool usage breakdown')
    views.add_argument('--languages', action='store_true',
                      help='LOC by language')
    views.add_argument('--efficiency', action='store_true',
                      help='Productivity metrics')
    views.add_argument('--errors', action='store_true',
                      help='Error analysis')
    views.add_argument('--hourly', action='store_true',
                      help='Activity by hour')
    views.add_argument('--sessions', action='store_true',
                      help='List recent sessions')
    views.add_argument('--forecast', action='store_true',
                      help='Spend projection')
    views.add_argument('--thinking', action='store_true',
                      help='Extended thinking analysis')
    views.add_argument('--models', action='store_true',
                      help='Model comparison')
    views.add_argument('--cost-breakdown', action='store_true',
                      help='Cost breakdown by token type')
    views.add_argument('--truncation', action='store_true',
                      help='Truncation/stop reason analysis')
    views.add_argument('--files', action='store_true',
                      help='File hotspot analysis')
    views.add_argument('--branches', action='store_true',
                      help='Branch-aware analytics')
    views.add_argument('--versions', action='store_true',
                      help='CC version impact analysis')
    views.add_argument('--user-types', action='store_true',
                      help='Human vs AI turn breakdown')
    views.add_argument('--sidechains', action='store_true',
                      help='Sidechain/branching analysis')
    views.add_argument('--cache-tiers', action='store_true',
                      help='Ephemeral cache tier analysis')
    views.add_argument('--skills', action='store_true',
                      help='Skill invocation analytics')
    views.add_argument('--db-stats', action='store_true',
                      help='Database statistics')

    # Session-specific views
    parser.add_argument('--session', metavar='ID',
                       help='Show session details')
    parser.add_argument('--replay', metavar='ID',
                       help='Replay session turn-by-turn')

    # Comparison
    parser.add_argument('--compare', metavar='PERIOD',
                       help='Compare periods (last-week, last-month, DATE..DATE)')
    parser.add_argument('--by-project', action='store_true',
                       help='Break down comparison by project')
    parser.add_argument('--diff', metavar='FILE',
                       help='Compare against snapshot file')

    # Trend
    parser.add_argument('--trend', metavar='METRIC',
                       help='Show trend for metric')
    parser.add_argument('--last', metavar='PERIOD',
                       help='Period for trend (e.g., 8w)')

    # Experiment tags
    parser.add_argument('--tag', metavar='NAME',
                       help='Tag current sessions')
    parser.add_argument('--tag-range', metavar='NAME',
                       help='Tag date range')
    parser.add_argument('--compare-tags', nargs=2, metavar=('TAG_A', 'TAG_B'),
                       help='Compare two experiment tags')

    # Date filters
    date_filters = parser.add_argument_group('date filters')
    date_filters.add_argument('--today', action='store_true',
                             help='Filter to today')
    date_filters.add_argument('--yesterday', action='store_true',
                             help='Filter to yesterday')
    date_filters.add_argument('--this-week', action='store_true',
                             help='Filter to this week')
    date_filters.add_argument('--last-week', action='store_true',
                             help='Filter to last week')
    date_filters.add_argument('--this-month', action='store_true',
                             help='Filter to this month')
    date_filters.add_argument('--last-month', action='store_true',
                             help='Filter to last month')
    date_filters.add_argument('--from', dest='date_from', metavar='DATE',
                             help='Start date (YYYY-MM-DD)')
    date_filters.add_argument('--to', dest='date_to', metavar='DATE',
                             help='End date (YYYY-MM-DD)')

    # Sort and filter
    parser.add_argument('--project', metavar='PATTERN',
                       help='Filter by project name')
    parser.add_argument('--sort', metavar='FIELD',
                       help='Sort by field')

    # Output options
    parser.add_argument('--json', action='store_true',
                       help='Output as JSON')
    parser.add_argument('--export', metavar='FILE',
                       help='Export to CSV file')
    parser.add_argument('--no-color', action='store_true',
                       help='Disable colors')

    # ETL control
    parser.add_argument('--rebuild', action='store_true',
                       help='Force full re-ETL')
    parser.add_argument('--verbose', '-v', action='store_true',
                       help='Verbose output')

    # Web dashboard
    parser.add_argument('--serve', action='store_true',
                       help='Start web dashboard server')
    parser.add_argument('--port', type=int, default=8080,
                       help='Port for web dashboard (default: 8080)')
    parser.add_argument('--host', default='0.0.0.0',
                       help='Host for web dashboard (default: 0.0.0.0)')
    parser.add_argument('--no-browser', action='store_true',
                       help='Don\'t open browser on serve')

    # Real-time monitoring
    parser.add_argument('--watch', action='store_true',
                       help='Watch mode: continuously monitor for changes')
    parser.add_argument('--force-scan', action='store_true',
                       help='Force re-scan of recently modified files')
    parser.add_argument('--poll-interval', type=int, default=5,
                       help='Poll interval in seconds for watch mode (default: 5)')
    parser.add_argument('--recent-hours', type=int, default=24,
                       help='Process files modified within N hours (default: 24)')

    return parser


def parse_date_filters(args) -> Tuple[Optional[datetime], Optional[datetime]]:
    """Parse date filter arguments into datetime range."""
    now = datetime.now()
    date_from = None
    date_to = None

    if args.today:
        date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = now
    elif args.yesterday:
        yesterday = now - timedelta(days=1)
        date_from = yesterday.replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = yesterday.replace(hour=23, minute=59, second=59)
    elif args.this_week:
        # Monday of this week
        days_since_monday = now.weekday()
        date_from = (now - timedelta(days=days_since_monday)).replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = now
    elif args.last_week:
        days_since_monday = now.weekday()
        last_monday = now - timedelta(days=days_since_monday + 7)
        date_from = last_monday.replace(hour=0, minute=0, second=0, microsecond=0)
        date_to = (last_monday + timedelta(days=6)).replace(hour=23, minute=59, second=59)
    elif args.this_month:
        date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        date_to = now
    elif args.last_month:
        first_of_this_month = now.replace(day=1)
        last_day_prev_month = first_of_this_month - timedelta(days=1)
        date_from = last_day_prev_month.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        date_to = last_day_prev_month.replace(hour=23, minute=59, second=59)
    elif args.date_from:
        date_from = datetime.strptime(args.date_from, '%Y-%m-%d')
        if args.date_to:
            date_to = datetime.strptime(args.date_to, '%Y-%m-%d')
        else:
            date_to = now

    return date_from, date_to


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    # Check cleanup period setting
    warning = check_claude_settings()
    if warning:
        print(warning)
        print()

    # Load configuration
    config = load_config()
    color_enabled = not args.no_color

    # Handle web dashboard
    if args.serve:
        _run_serve(config, args)
        return

    # Handle watch mode
    if args.watch:
        from ccwap.etl.watcher import run_watch_mode
        run_watch_mode(
            poll_interval=args.poll_interval,
            verbose=args.verbose,
            recent_hours=args.recent_hours
        )
        return

    # Handle force-scan mode
    if args.force_scan:
        from ccwap.etl.watcher import force_scan_recent
        result = force_scan_recent(
            config=config,
            hours=args.recent_hours,
            verbose=args.verbose
        )
        if args.verbose:
            print(f"Force scan: {result['message']}")
        # Continue with normal ETL which will now reprocess these files

    # Run ETL first (unless just checking db-stats)
    if not args.db_stats:
        try:
            from ccwap.etl import run_etl

            if args.verbose:
                print("Running ETL pipeline...")

            stats = run_etl(
                force_rebuild=args.rebuild,
                verbose=args.verbose,
                config=config,
                recent_hours=args.recent_hours if args.force_scan else None
            )

            if args.verbose:
                print(f"ETL complete: {stats['files_processed']} files processed, "
                      f"{stats['turns_inserted']} turns inserted")
                print()

        except FileNotFoundError as e:
            print(f"Error: {e}")
            print("Make sure Claude Code has been run at least once.")
            sys.exit(1)

    # Get database connection
    db_path = get_database_path(config)
    if not db_path.exists():
        print(f"Error: Database not found at {db_path}")
        print("Run 'ccwap' first to initialize the database.")
        sys.exit(1)

    conn = get_connection(db_path)
    ensure_database(conn)

    # Parse date filters
    date_from, date_to = parse_date_filters(args)

    try:
        # Handle CSV export
        if args.export:
            from ccwap.output.csv_export import export_report

            # Determine report type from flags
            if args.daily:
                report_type = 'daily'
            elif args.projects:
                report_type = 'projects'
            elif args.tools:
                report_type = 'tools'
            elif args.errors:
                report_type = 'errors'
            elif args.sessions:
                report_type = 'sessions'
            else:
                report_type = 'summary'

            result = export_report(conn, args.export, report_type,
                                  date_from, date_to, args.project)
            print(result)
            return

        # Dispatch to appropriate report
        if args.all:
            from ccwap.reports.summary import generate_summary
            from ccwap.reports.daily import generate_daily
            from ccwap.reports.projects import generate_projects

            print(generate_summary(conn, config, color_enabled))
            print()
            print(generate_daily(conn, config, date_from, date_to, color_enabled))
            print()
            print(generate_projects(conn, config, date_from, date_to,
                                   args.project, args.sort or 'cost', color_enabled))

        elif args.daily:
            from ccwap.reports.daily import generate_daily
            print(generate_daily(conn, config, date_from, date_to, color_enabled))

        elif args.weekly:
            from ccwap.reports.weekly import generate_weekly
            print(generate_weekly(conn, config, date_from, date_to, color_enabled))

        elif args.projects:
            from ccwap.reports.projects import generate_projects
            print(generate_projects(conn, config, date_from, date_to,
                                   args.project, args.sort or 'cost', color_enabled))

        elif args.tools:
            from ccwap.reports.tools import generate_tools
            print(generate_tools(conn, config, date_from, date_to, color_enabled))

        elif args.languages:
            from ccwap.reports.languages import generate_languages
            print(generate_languages(conn, config, date_from, date_to, color_enabled))

        elif args.efficiency:
            from ccwap.reports.efficiency import generate_efficiency
            print(generate_efficiency(conn, config, date_from, date_to, color_enabled))

        elif args.errors:
            from ccwap.reports.errors import generate_errors
            print(generate_errors(conn, config, date_from, date_to, color_enabled))

        elif args.hourly:
            from ccwap.reports.hourly import generate_hourly
            print(generate_hourly(conn, config, date_from, date_to, color_enabled))

        elif args.thinking:
            from ccwap.reports.thinking import generate_thinking
            print(generate_thinking(conn, config, date_from, date_to, color_enabled))

        elif args.models:
            from ccwap.reports.models import generate_models
            print(generate_models(conn, config, date_from, date_to, color_enabled))

        elif args.cost_breakdown:
            from ccwap.reports.cost_breakdown import generate_cost_breakdown
            print(generate_cost_breakdown(conn, config, date_from, date_to, color_enabled))

        elif args.truncation:
            from ccwap.reports.truncation import generate_truncation
            print(generate_truncation(conn, config, date_from, date_to, color_enabled))

        elif args.files:
            from ccwap.reports.files import generate_files
            print(generate_files(conn, config, date_from, date_to, color_enabled))

        elif args.branches:
            from ccwap.reports.branches import generate_branches
            print(generate_branches(conn, config, date_from, date_to, color_enabled))

        elif args.versions:
            from ccwap.reports.versions import generate_versions
            print(generate_versions(conn, config, date_from, date_to, color_enabled))

        elif args.user_types:
            from ccwap.reports.user_types import generate_user_types
            print(generate_user_types(conn, config, date_from, date_to, color_enabled))

        elif args.sidechains:
            from ccwap.reports.sidechains import generate_sidechains
            print(generate_sidechains(conn, config, date_from, date_to, color_enabled))

        elif args.cache_tiers:
            from ccwap.reports.cache_tiers import generate_cache_tiers
            print(generate_cache_tiers(conn, config, date_from, date_to, color_enabled))

        elif args.skills:
            from ccwap.reports.skills import generate_skills
            print(generate_skills(conn, config, date_from, date_to, color_enabled))

        elif args.sessions:
            from ccwap.reports.sessions import generate_sessions_list
            print(generate_sessions_list(conn, config, date_from, date_to,
                                        args.project, color_enabled))

        elif args.session:
            from ccwap.reports.sessions import generate_session_detail
            print(generate_session_detail(conn, args.session, config, color_enabled))

        elif args.replay:
            from ccwap.reports.sessions import generate_session_replay
            print(generate_session_replay(conn, args.replay, config, color_enabled))

        elif args.forecast:
            from ccwap.reports.forecast import generate_forecast
            print(generate_forecast(conn, config, color_enabled))

        elif args.compare:
            from ccwap.reports.compare import generate_compare
            print(generate_compare(conn, args.compare, config, args.by_project, color_enabled))

        elif args.trend:
            from ccwap.reports.trend import generate_trend
            print(generate_trend(conn, args.trend, config, args.last, color_enabled))

        elif args.tag:
            from ccwap.reports.tags import tag_sessions
            count = tag_sessions(conn, args.tag, date_from=date_from, date_to=date_to)
            print(f"Tagged {count} sessions with '{args.tag}'")

        elif args.compare_tags:
            from ccwap.reports.tags import compare_tags
            print(compare_tags(conn, args.compare_tags[0], args.compare_tags[1], config, color_enabled))

        elif args.diff:
            from ccwap.output.snapshot import generate_diff
            print(generate_diff(conn, args.diff, config, color_enabled))

        elif args.db_stats:
            _print_db_stats(conn, color_enabled)

        else:
            # Default: show summary
            from ccwap.reports.summary import generate_summary
            print(generate_summary(conn, config, color_enabled))

    finally:
        conn.close()


def _run_serve(config, args):
    """Start the web dashboard server."""
    try:
        import uvicorn
    except ImportError:
        print("Error: Web dashboard requires additional dependencies.")
        print("Install them with: python -m pip install fastapi uvicorn[standard] aiosqlite pydantic")
        sys.exit(1)

    from ccwap.etl import run_etl

    # Run incremental ETL first
    print("Running ETL pipeline...")
    try:
        stats = run_etl(config=config, verbose=args.verbose)
        print(f"ETL complete: {stats['files_processed']} files processed, "
              f"{stats['turns_inserted']} turns inserted")
    except FileNotFoundError as e:
        print(f"Warning: {e}")
        print("Starting server without data...")

    from ccwap.server.app import create_app
    app = create_app(config=config)

    url = f"http://{args.host}:{args.port}"
    print(f"\nStarting CCWAP Dashboard at {url}")
    print("Press Ctrl+C to stop\n")

    if not args.no_browser:
        import webbrowser
        import threading
        threading.Timer(1.0, webbrowser.open, args=[url]).start()

    uvicorn.run(app, host=args.host, port=args.port, log_level="info")


def _print_db_stats(conn, color_enabled: bool = True):
    """Print database statistics."""
    from ccwap.output.formatter import format_number, bold

    print(bold("DATABASE STATISTICS", color_enabled))
    print("-" * 40)

    tables = ['sessions', 'turns', 'tool_calls', 'experiment_tags', 'daily_summaries', 'etl_state', 'snapshots']
    for table in tables:
        cursor = conn.execute(f"SELECT COUNT(*) FROM {table}")
        count = cursor.fetchone()[0]
        print(f"{table:20} {format_number(count):>10} rows")


if __name__ == '__main__':
    main()
