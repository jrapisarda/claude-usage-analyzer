"""
Daily report for CCWAP.

Generates the --daily view with rolling 30-day breakdown.
FIXES BUG 7: Always includes today's data.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens, format_percentage,
    format_table, bold, colorize, Colors, create_bar
)


def generate_daily(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate daily breakdown report.

    Shows rolling 30 days, always including today.
    FIXES BUG 7: No mtime optimization that skips recent files.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date (defaults to 30 days ago)
        date_to: End date (defaults to today)
        color_enabled: Whether to apply colors
    """
    if date_to is None:
        date_to = datetime.now()
    if date_from is None:
        date_from = date_to - timedelta(days=30)

    lines = []
    lines.append(bold("DAILY BREAKDOWN", color_enabled))
    lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Query daily data
    cursor = conn.execute("""
        SELECT
            date(timestamp) as date,
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as turns,
            SUM(CASE WHEN entry_type = 'user' THEN 1 ELSE 0 END) as user_turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read,
            SUM(cache_write_tokens) as cache_write,
            SUM(cost) as cost,
            SUM(thinking_chars) as thinking_chars,
            SUM(CASE WHEN stop_reason = 'max_tokens' THEN 1 ELSE 0 END) as truncated
        FROM turns
        WHERE date(timestamp) >= date(?)
        AND date(timestamp) <= date(?)
        GROUP BY date(timestamp)
        ORDER BY date DESC
    """, (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n" + lines[1] + "\n\nNo data for this period."

    # Find max cost for bar chart
    max_cost = max(r['cost'] or 0 for r in rows)

    # Calculate 7-day rolling average for anomaly detection
    costs = [r['cost'] or 0 for r in rows]
    today_str = datetime.now().strftime('%Y-%m-%d')

    # Compute 30-day average cost for anomaly flagging
    avg_30d_cost = sum(costs) / len(costs) if costs else 0

    # Prepare table data
    headers = ['Date', 'Sessions', 'Turns', 'Tokens', 'Cost', 'Think', 'Trunc', 'Bar']
    alignments = ['l', 'r', 'r', 'r', 'r', 'r', 'r', 'l']
    table_rows = []

    for r in rows:
        date_str = r['date']
        is_today = date_str == today_str

        # Today indicator
        if is_today:
            date_display = colorize(f"{date_str} *", Colors.GREEN, color_enabled)
        else:
            date_display = date_str

        total_tokens = (r['input_tokens'] or 0) + (r['output_tokens'] or 0)
        cost = r['cost'] or 0
        cost_str = format_currency(cost)

        # Color high-cost days
        if cost > max_cost * 0.8:
            cost_str = colorize(cost_str, Colors.YELLOW, color_enabled)

        # Anomaly detection: flag days with cost > 2x the 30-day average
        if avg_30d_cost > 0 and cost > 2 * avg_30d_cost:
            cost_str = cost_str + " " + colorize("!!", Colors.RED, color_enabled)

        bar = create_bar(cost, max_cost, width=15)

        # Thinking chars
        think_str = format_tokens(r['thinking_chars'] or 0)

        # Truncation count
        trunc_count = r['truncated'] or 0
        trunc_str = str(trunc_count)
        if trunc_count > 0:
            trunc_str = colorize(trunc_str, Colors.RED, color_enabled)

        table_rows.append([
            date_display,
            format_number(r['sessions'] or 0),
            format_number(r['turns'] or 0),
            format_tokens(total_tokens),
            cost_str,
            think_str,
            trunc_str,
            bar,
        ])

    # Add totals row
    total_sessions = sum(r['sessions'] or 0 for r in rows)
    total_turns = sum(r['turns'] or 0 for r in rows)
    total_tokens = sum((r['input_tokens'] or 0) + (r['output_tokens'] or 0) for r in rows)
    total_cost = sum(r['cost'] or 0 for r in rows)
    total_thinking = sum(r['thinking_chars'] or 0 for r in rows)
    total_truncated = sum(r['truncated'] or 0 for r in rows)

    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_number(total_sessions), color_enabled),
        bold(format_number(total_turns), color_enabled),
        bold(format_tokens(total_tokens), color_enabled),
        bold(format_currency(total_cost), color_enabled),
        bold(format_tokens(total_thinking), color_enabled),
        bold(str(total_truncated), color_enabled),
        '',
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # Summary stats
    lines.append("")
    avg_daily = total_cost / len(rows) if rows else 0
    lines.append(f"Average daily cost: {format_currency(avg_daily)}")

    lines.append(f"Total thinking chars: {format_tokens(total_thinking)}")

    trunc_rate = (total_truncated / total_turns * 100) if total_turns > 0 else 0
    trunc_rate_str = format_percentage(trunc_rate)
    if trunc_rate >= 10:
        trunc_rate_str = colorize(trunc_rate_str, Colors.RED, color_enabled)
    elif trunc_rate >= 5:
        trunc_rate_str = colorize(trunc_rate_str, Colors.YELLOW, color_enabled)
    else:
        trunc_rate_str = colorize(trunc_rate_str, Colors.GREEN, color_enabled)
    lines.append(f"Truncation rate: {trunc_rate_str}")

    return '\n'.join(lines)
