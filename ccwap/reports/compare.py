"""
Comparison report for CCWAP.

Generates the --compare view for period comparisons.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, Tuple

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens, format_delta,
    format_table, bold, colorize, Colors
)


def parse_compare_period(period: str) -> Tuple[datetime, datetime, datetime, datetime]:
    """
    Parse comparison period string into date ranges.

    Supports:
    - 'last-week': This week vs last week
    - 'last-month': This month vs last month
    - 'DATE1..DATE2': Custom range (compares to same duration before)

    Returns:
        (current_from, current_to, previous_from, previous_to)
    """
    now = datetime.now()

    if period == 'last-week':
        # Current: this week (Mon-now)
        days_since_monday = now.weekday()
        current_from = (now - timedelta(days=days_since_monday)).replace(
            hour=0, minute=0, second=0, microsecond=0)
        current_to = now

        # Previous: last week (Mon-Sun)
        previous_from = current_from - timedelta(days=7)
        previous_to = current_from - timedelta(seconds=1)

    elif period == 'last-month':
        # Current: this month
        current_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        current_to = now

        # Previous: last month
        previous_to = current_from - timedelta(seconds=1)
        previous_from = previous_to.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    elif '..' in period:
        # Custom range: DATE1..DATE2
        parts = period.split('..')
        if len(parts) != 2:
            raise ValueError(f"Invalid period format: {period}")

        current_from = datetime.strptime(parts[0], '%Y-%m-%d')
        current_to = datetime.strptime(parts[1], '%Y-%m-%d').replace(
            hour=23, minute=59, second=59)

        # Previous: same duration before
        duration = current_to - current_from
        previous_to = current_from - timedelta(seconds=1)
        previous_from = previous_to - duration

    else:
        raise ValueError(f"Unknown period: {period}. Use 'last-week', 'last-month', or 'DATE..DATE'")

    return current_from, current_to, previous_from, previous_to


def generate_compare(
    conn: sqlite3.Connection,
    period: str,
    config: Dict[str, Any],
    by_project: bool = False,
    color_enabled: bool = True
) -> str:
    """
    Generate period comparison report.

    Args:
        conn: Database connection
        period: Period to compare (last-week, last-month, DATE..DATE)
        config: Configuration dict
        by_project: Whether to break down by project
        color_enabled: Whether to apply colors
    """
    lines = []

    try:
        current_from, current_to, previous_from, previous_to = parse_compare_period(period)
    except ValueError as e:
        return f"Error: {e}"

    lines.append(bold(f"PERIOD COMPARISON: {period}", color_enabled))
    lines.append("=" * 60)
    lines.append("")
    lines.append(f"Current:  {current_from.strftime('%Y-%m-%d')} to {current_to.strftime('%Y-%m-%d')}")
    lines.append(f"Previous: {previous_from.strftime('%Y-%m-%d')} to {previous_to.strftime('%Y-%m-%d')}")
    lines.append("")

    if by_project:
        return _compare_by_project(conn, current_from, current_to, previous_from, previous_to, lines, color_enabled)

    # Overall comparison
    current_stats = _get_period_stats(conn, current_from, current_to)
    previous_stats = _get_period_stats(conn, previous_from, previous_to)

    headers = ['Metric', 'Previous', 'Current', 'Change']
    alignments = ['l', 'r', 'r', 'r']
    table_rows = []

    metrics = [
        ('Sessions', 'sessions', format_number),
        ('Turns', 'turns', format_number),
        ('Input Tokens', 'input_tokens', format_tokens),
        ('Output Tokens', 'output_tokens', format_tokens),
        ('Cache Read', 'cache_read', format_tokens),
        ('Total Cost', 'cost', format_currency),
        ('Tool Calls', 'tool_calls', format_number),
        ('LOC Written', 'loc_written', format_number),
    ]

    for label, key, fmt in metrics:
        prev_val = previous_stats.get(key, 0)
        curr_val = current_stats.get(key, 0)
        delta = format_delta(curr_val, prev_val, color_enabled=color_enabled)

        table_rows.append([label, fmt(prev_val), fmt(curr_val), delta])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # Summary
    lines.append("")
    cost_change = current_stats.get('cost', 0) - previous_stats.get('cost', 0)
    if cost_change > 0:
        change_str = colorize(f"+{format_currency(cost_change)}", Colors.RED, color_enabled)
    else:
        change_str = colorize(f"{format_currency(cost_change)}", Colors.GREEN, color_enabled)
    lines.append(f"Cost change: {change_str}")

    return '\n'.join(lines)


def _get_period_stats(
    conn: sqlite3.Connection,
    date_from: datetime,
    date_to: datetime
) -> Dict[str, Any]:
    """Get aggregated statistics for a date period."""
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read,
            SUM(cost) as cost
        FROM turns
        WHERE date(timestamp) >= date(?)
        AND date(timestamp) <= date(?)
    """, (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

    row = cursor.fetchone()

    # Get tool call stats
    tc_cursor = conn.execute("""
        SELECT
            COUNT(*) as tool_calls,
            SUM(loc_written) as loc_written
        FROM tool_calls
        WHERE date(timestamp) >= date(?)
        AND date(timestamp) <= date(?)
    """, (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

    tc_row = tc_cursor.fetchone()

    return {
        'sessions': row['sessions'] or 0,
        'turns': row['turns'] or 0,
        'input_tokens': row['input_tokens'] or 0,
        'output_tokens': row['output_tokens'] or 0,
        'cache_read': row['cache_read'] or 0,
        'cost': row['cost'] or 0,
        'tool_calls': tc_row['tool_calls'] or 0,
        'loc_written': tc_row['loc_written'] or 0,
    }


def _compare_by_project(
    conn: sqlite3.Connection,
    current_from: datetime,
    current_to: datetime,
    previous_from: datetime,
    previous_to: datetime,
    lines: list,
    color_enabled: bool
) -> str:
    """Generate comparison broken down by project."""
    lines.append(bold("BY PROJECT", color_enabled))
    lines.append("-" * 60)

    # Get all projects in both periods
    cursor = conn.execute("""
        SELECT DISTINCT s.project_display
        FROM sessions s
        JOIN turns t ON t.session_id = s.session_id
        WHERE (date(t.timestamp) >= date(?) AND date(t.timestamp) <= date(?))
           OR (date(t.timestamp) >= date(?) AND date(t.timestamp) <= date(?))
    """, (previous_from.strftime('%Y-%m-%d'), previous_to.strftime('%Y-%m-%d'),
          current_from.strftime('%Y-%m-%d'), current_to.strftime('%Y-%m-%d')))

    projects = [r['project_display'] for r in cursor.fetchall()]

    if not projects:
        return '\n'.join(lines) + "\n\nNo project data found."

    headers = ['Project', 'Prev Cost', 'Curr Cost', 'Change']
    alignments = ['l', 'r', 'r', 'r']
    table_rows = []

    for project in projects:
        prev_stats = _get_project_period_stats(conn, project, previous_from, previous_to)
        curr_stats = _get_project_period_stats(conn, project, current_from, current_to)

        prev_cost = prev_stats.get('cost', 0)
        curr_cost = curr_stats.get('cost', 0)
        delta = format_delta(curr_cost, prev_cost, color_enabled=color_enabled)

        name = project or 'Unknown'
        if len(name) > 35:
            name = name[:32] + '...'

        table_rows.append([name, format_currency(prev_cost), format_currency(curr_cost), delta])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    return '\n'.join(lines)


def _get_project_period_stats(
    conn: sqlite3.Connection,
    project: str,
    date_from: datetime,
    date_to: datetime
) -> Dict[str, Any]:
    """Get statistics for a specific project in a date period."""
    cursor = conn.execute("""
        SELECT SUM(t.cost) as cost
        FROM turns t
        JOIN sessions s ON s.session_id = t.session_id
        WHERE s.project_display = ?
        AND date(t.timestamp) >= date(?)
        AND date(t.timestamp) <= date(?)
    """, (project, date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

    row = cursor.fetchone()
    return {'cost': row['cost'] or 0}
