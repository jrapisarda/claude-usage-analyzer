"""
Tools report for CCWAP.

Generates the --tools view with tool usage frequency and success rates.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage,
    format_table, bold, colorize, Colors, create_bar
)


def generate_tools(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate tool usage breakdown report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("TOOL USAGE", color_enabled))

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

    # Query tool stats
    cursor = conn.execute(f"""
        SELECT
            tool_name,
            COUNT(*) as calls,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
            SUM(loc_written) as loc_written,
            SUM(lines_added) as lines_added,
            SUM(lines_deleted) as lines_deleted
        FROM tool_calls
        WHERE 1=1 {date_filter}
        GROUP BY tool_name
        ORDER BY calls DESC
    """, params)

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo tool usage data found."

    # Find max calls for bar chart
    max_calls = max(r['calls'] for r in rows)
    total_calls = sum(r['calls'] for r in rows)

    # Prepare table data
    headers = ['Tool', 'Calls', '%', 'Success', 'LOC', 'Bar']
    alignments = ['l', 'r', 'r', 'r', 'r', 'l']
    table_rows = []

    for r in rows:
        tool_name = r['tool_name']
        calls = r['calls']
        successes = r['successes'] or 0
        failures = r['failures'] or 0
        loc = r['loc_written'] or 0

        # Calculate success rate
        success_rate = (successes / calls * 100) if calls > 0 else 0
        success_str = format_percentage(success_rate, 1)

        # Color low success rates
        if success_rate < 90 and failures > 0:
            success_str = colorize(success_str, Colors.YELLOW, color_enabled)
        if success_rate < 80 and failures > 0:
            success_str = colorize(success_str, Colors.RED, color_enabled)

        # Calculate percentage of total
        pct = (calls / total_calls * 100) if total_calls > 0 else 0

        bar = create_bar(calls, max_calls, width=15)

        table_rows.append([
            tool_name,
            format_number(calls),
            format_percentage(pct, 1),
            success_str,
            format_number(loc) if loc > 0 else '-',
            bar,
        ])

    # Add totals row
    total_successes = sum(r['successes'] or 0 for r in rows)
    total_loc = sum(r['loc_written'] or 0 for r in rows)
    overall_success = (total_successes / total_calls * 100) if total_calls > 0 else 0

    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_number(total_calls), color_enabled),
        bold('100.0%', color_enabled),
        bold(format_percentage(overall_success, 1), color_enabled),
        bold(format_number(total_loc), color_enabled),
        '',
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # Top error-prone tools
    error_tools = [r for r in rows if (r['failures'] or 0) > 0]
    if error_tools:
        lines.append("")
        lines.append(bold("ERROR-PRONE TOOLS", color_enabled))
        lines.append("-" * 40)
        for r in sorted(error_tools, key=lambda x: x['failures'] or 0, reverse=True)[:5]:
            failures = r['failures'] or 0
            total = r['calls']
            rate = (failures / total * 100) if total > 0 else 0
            lines.append(f"{r['tool_name']:20} {failures:>5} errors ({format_percentage(rate, 1)})")

    return '\n'.join(lines)
