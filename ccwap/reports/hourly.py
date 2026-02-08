"""
Hourly report for CCWAP.

Generates the --hourly view with activity by hour of day.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_currency, format_percentage,
    bold, colorize, Colors, create_bar
)


def generate_hourly(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate activity by hour report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("ACTIVITY BY HOUR", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build query with optional date filters
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # Query hourly stats (using local time)
    cursor = conn.execute(f"""
        SELECT
            CAST(strftime('%H', timestamp, 'localtime') AS INTEGER) as hour,
            COUNT(*) as turns,
            COUNT(DISTINCT session_id) as sessions,
            SUM(CASE WHEN entry_type = 'user' THEN 1 ELSE 0 END) as user_turns,
            SUM(input_tokens + output_tokens) as tokens,
            SUM(cost) as cost
        FROM turns
        WHERE 1=1 {date_filter}
        GROUP BY hour
        ORDER BY hour
    """, params)

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo hourly data found."

    # Create a full 24-hour view
    hour_data = {r['hour']: r for r in rows}
    max_turns = max(r['turns'] for r in rows)
    total_turns = sum(r['turns'] for r in rows)

    # Header
    lines.append(f"{'Hour':6} {'Turns':>7} {'%':>6} {'Cost':>10} {'Activity':30}")
    lines.append("-" * 60)

    for hour in range(24):
        if hour in hour_data:
            r = hour_data[hour]
            turns = r['turns']
            cost = r['cost'] or 0
            pct = (turns / total_turns * 100) if total_turns > 0 else 0
            bar = create_bar(turns, max_turns, width=30)

            # Color peak hours
            if pct > 10:
                bar = colorize(bar, Colors.GREEN, color_enabled)
            elif pct > 5:
                bar = colorize(bar, Colors.YELLOW, color_enabled)
        else:
            turns = 0
            cost = 0
            pct = 0
            bar = create_bar(0, 1, width=30)

        hour_str = f"{hour:02d}:00"
        lines.append(f"{hour_str:6} {format_number(turns):>7} {format_percentage(pct, 1):>6} {format_currency(cost):>10} {bar}")

    # Summary
    lines.append("-" * 60)
    total_cost = sum(r['cost'] or 0 for r in rows)
    lines.append(f"{'TOTAL':6} {format_number(total_turns):>7} {'100.0%':>6} {format_currency(total_cost):>10}")
    lines.append("")

    # Peak hours analysis
    sorted_hours = sorted(rows, key=lambda x: x['turns'], reverse=True)
    peak_hours = sorted_hours[:3]

    lines.append(bold("PEAK ACTIVITY HOURS", color_enabled))
    lines.append("-" * 40)
    for r in peak_hours:
        hour = r['hour']
        turns = r['turns']
        pct = (turns / total_turns * 100) if total_turns > 0 else 0
        lines.append(f"{hour:02d}:00 - {hour:02d}:59  {format_number(turns):>6} turns ({format_percentage(pct, 1)})")

    # Quiet hours
    if len(sorted_hours) > 3:
        lines.append("")
        lines.append(bold("QUIET HOURS", color_enabled))
        lines.append("-" * 40)
        quiet_hours = [r for r in sorted_hours if r['turns'] < total_turns * 0.02]
        if quiet_hours:
            quiet_list = sorted([r['hour'] for r in quiet_hours])
            # Group consecutive hours
            ranges = []
            start = quiet_list[0]
            end = quiet_list[0]
            for h in quiet_list[1:]:
                if h == end + 1:
                    end = h
                else:
                    ranges.append((start, end))
                    start = end = h
            ranges.append((start, end))

            for start, end in ranges:
                if start == end:
                    lines.append(f"{start:02d}:00")
                else:
                    lines.append(f"{start:02d}:00 - {end:02d}:59")

    return '\n'.join(lines)
