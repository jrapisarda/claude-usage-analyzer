"""
Weekly report for CCWAP.

Generates the --weekly view with ISO week aggregation and WoW deltas.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens, format_percentage,
    format_table, format_delta, bold, colorize, Colors
)


def generate_weekly(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate weekly breakdown report with WoW deltas.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date (defaults to 8 weeks ago)
        date_to: End date (defaults to today)
        color_enabled: Whether to apply colors
    """
    if date_to is None:
        date_to = datetime.now()
    if date_from is None:
        date_from = date_to - timedelta(weeks=8)

    lines = []
    lines.append(bold("WEEKLY BREAKDOWN", color_enabled))
    lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Query weekly data using ISO week
    cursor = conn.execute("""
        SELECT
            strftime('%Y-W%W', timestamp) as week,
            MIN(date(timestamp)) as week_start,
            MAX(date(timestamp)) as week_end,
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
        GROUP BY strftime('%Y-W%W', timestamp)
        ORDER BY week DESC
    """, (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n" + lines[1] + "\n\nNo data for this period."

    # Prepare table data with WoW deltas
    headers = ['Week', 'Sessions', 'Turns', 'Tokens', 'Cost', 'Think', 'Trunc', 'WoW Δ']
    alignments = ['l', 'r', 'r', 'r', 'r', 'r', 'r', 'r']
    table_rows = []

    for i, r in enumerate(rows):
        week_str = r['week']
        total_tokens = (r['input_tokens'] or 0) + (r['output_tokens'] or 0)
        cost = r['cost'] or 0

        # Calculate WoW delta (compare to previous week)
        if i + 1 < len(rows):
            prev_cost = rows[i + 1]['cost'] or 0
            wow_delta = format_delta(cost, prev_cost, color_enabled=color_enabled)
        else:
            wow_delta = "N/A"

        # Thinking chars
        think_str = format_tokens(r['thinking_chars'] or 0)

        # Truncation count
        trunc_count = r['truncated'] or 0
        trunc_str = str(trunc_count)
        if trunc_count > 0:
            trunc_str = colorize(trunc_str, Colors.RED, color_enabled)

        table_rows.append([
            week_str,
            format_number(r['sessions'] or 0),
            format_number(r['turns'] or 0),
            format_tokens(total_tokens),
            format_currency(cost),
            think_str,
            trunc_str,
            wow_delta,
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
    avg_weekly = total_cost / len(rows) if rows else 0
    lines.append(f"Average weekly cost: {format_currency(avg_weekly)}")

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
