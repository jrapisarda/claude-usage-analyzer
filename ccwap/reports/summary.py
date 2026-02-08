"""
Summary report for CCWAP.

Generates the default summary view and the --all report.
"""

import sqlite3
from typing import Dict, Any

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens, format_percentage,
    print_header, print_section, bold, colorize, Colors
)


def generate_summary(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    color_enabled: bool = True
) -> str:
    """
    Generate the main summary view.

    Shows all-time totals, today's stats, and model breakdown.
    """
    lines = []

    # Header
    lines.append(print_header("CLAUDE CODE WORKFLOW ANALYTICS", color_enabled=color_enabled))
    lines.append("")

    # All-time stats
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read,
            SUM(cache_write_tokens) as cache_write,
            SUM(cost) as total_cost,
            SUM(thinking_chars) as thinking_chars
        FROM turns
    """)
    row = cursor.fetchone()

    lines.append(bold("ALL-TIME TOTALS", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Sessions:        {format_number(row['sessions'] or 0)}")
    lines.append(f"Turns:           {format_number(row['turns'] or 0)}")
    lines.append(f"Input Tokens:    {format_tokens(row['input_tokens'] or 0)}")
    lines.append(f"Output Tokens:   {format_tokens(row['output_tokens'] or 0)}")
    lines.append(f"Cache Read:      {format_tokens(row['cache_read'] or 0)}")
    lines.append(f"Cache Write:     {format_tokens(row['cache_write'] or 0)}")
    lines.append(f"Total Cost:      {colorize(format_currency(row['total_cost'] or 0), Colors.CYAN, color_enabled)}")
    lines.append("")

    # Cache efficiency
    total_input = (row['input_tokens'] or 0) + (row['cache_read'] or 0)
    if total_input > 0:
        cache_hit_rate = (row['cache_read'] or 0) / total_input * 100
        lines.append(f"Cache Hit Rate:  {format_percentage(cache_hit_rate)}")
        lines.append("")

    # Today's stats
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as turns,
            SUM(cost) as cost
        FROM turns
        WHERE date(timestamp) = date('now')
    """)
    today_row = cursor.fetchone()

    today_cost = today_row['cost'] or 0
    today_indicator = colorize("*", Colors.GREEN, color_enabled)

    lines.append(bold(f"TODAY {today_indicator}", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Sessions:        {format_number(today_row['sessions'] or 0)}")
    lines.append(f"Turns:           {format_number(today_row['turns'] or 0)}")
    lines.append(f"Cost:            {format_currency(today_cost)}")
    lines.append("")

    # Model breakdown
    lines.append(bold("COST BY MODEL", color_enabled))
    lines.append("-" * 40)

    cursor = conn.execute("""
        SELECT
            model,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read,
            SUM(cache_write_tokens) as cache_write,
            SUM(cost) as cost
        FROM turns
        WHERE model IS NOT NULL
        GROUP BY model
        ORDER BY cost DESC
    """)

    for r in cursor.fetchall():
        model_name = r['model'] or 'unknown'
        # Shorten model name for display
        display_name = model_name.replace('claude-', '').replace('-20251101', '').replace('-20250514', '').replace('-20241022', '').replace('-20250929', '')
        cost_str = format_currency(r['cost'] or 0)
        lines.append(f"  {display_name:30} {cost_str:>10}")

    lines.append("")

    # Project summary
    lines.append(bold("TOP PROJECTS BY COST", color_enabled))
    lines.append("-" * 40)

    cursor = conn.execute("""
        SELECT
            s.project_display,
            COUNT(DISTINCT s.session_id) as sessions,
            SUM(t.cost) as cost
        FROM sessions s
        JOIN turns t ON t.session_id = s.session_id
        GROUP BY s.project_path
        ORDER BY cost DESC
        LIMIT 5
    """)

    for r in cursor.fetchall():
        project_name = r['project_display'] or 'Unknown'
        if len(project_name) > 30:
            project_name = project_name[:27] + '...'
        cost_str = format_currency(r['cost'] or 0)
        sessions_str = f"({r['sessions']} sessions)"
        lines.append(f"  {project_name:30} {cost_str:>10} {sessions_str}")

    return '\n'.join(lines)


def generate_totals_summary(conn: sqlite3.Connection) -> Dict[str, Any]:
    """
    Get totals for JSON export and comparisons.

    Returns dict with all aggregated metrics.
    """
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as turns,
            SUM(CASE WHEN entry_type = 'user' THEN 1 ELSE 0 END) as user_turns,
            SUM(CASE WHEN entry_type = 'assistant' THEN 1 ELSE 0 END) as assistant_turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(cache_write_tokens) as cache_write_tokens,
            SUM(cost) as cost,
            SUM(thinking_chars) as thinking_chars
        FROM turns
    """)
    row = cursor.fetchone()

    return dict(row)
