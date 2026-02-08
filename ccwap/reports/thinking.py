"""
Extended thinking analysis report for CCWAP.

Generates the --thinking view with thinking usage metrics.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, bold, colorize, Colors, create_bar
)

CHARS_PER_TOKEN = 4


def generate_thinking(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate extended thinking analysis report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("EXTENDED THINKING ANALYSIS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(t.timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(t.timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # Summary stats
    cursor = conn.execute(f"""
        SELECT
            SUM(t.thinking_chars) as total_thinking_chars,
            COUNT(CASE WHEN t.thinking_chars > 0 THEN 1 END) as turns_with_thinking,
            COUNT(*) as total_turns,
            SUM(CASE WHEN t.thinking_chars > 0 THEN t.cost ELSE 0 END) as thinking_cost
        FROM turns t
        WHERE 1=1 {date_filter}
    """, params)

    summary = cursor.fetchone()
    total_thinking_chars = summary['total_thinking_chars'] or 0
    turns_with_thinking = summary['turns_with_thinking'] or 0
    total_turns = summary['total_turns'] or 0
    thinking_cost = summary['thinking_cost'] or 0

    if total_turns == 0:
        return lines[0] + "\n\nNo data found."

    thinking_tokens = total_thinking_chars // CHARS_PER_TOKEN
    thinking_pct = (turns_with_thinking / total_turns * 100) if total_turns > 0 else 0

    lines.append(bold("SUMMARY", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Total thinking chars: {format_number(total_thinking_chars)}")
    lines.append(f"Est. thinking tokens: {format_tokens(thinking_tokens)}")
    lines.append(f"Turns with thinking:  {format_number(turns_with_thinking)}")
    lines.append(f"Thinking turn ratio:  {format_percentage(thinking_pct)}")
    lines.append(f"Thinking turn cost:   {format_currency(thinking_cost)}")
    lines.append("")

    # Thinking by model
    cursor = conn.execute(f"""
        SELECT
            t.model,
            COUNT(CASE WHEN t.thinking_chars > 0 THEN 1 END) as turns_with_thinking,
            SUM(t.thinking_chars) as thinking_chars,
            AVG(CASE WHEN t.thinking_chars > 0 THEN t.thinking_chars END) as avg_thinking_chars
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY t.model
        HAVING turns_with_thinking > 0
        ORDER BY thinking_chars DESC
    """, params)

    model_rows = cursor.fetchall()

    if model_rows:
        lines.append(bold("THINKING BY MODEL", color_enabled))
        headers = ['Model', 'Turns', 'Thinking Chars', 'Avg Chars/Turn', 'Tokens']
        alignments = ['l', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in model_rows:
            model = r['model'] or 'Unknown'
            if len(model) > 30:
                model = model[:27] + '...'
            chars = r['thinking_chars'] or 0
            avg_chars = r['avg_thinking_chars'] or 0
            tokens = chars // CHARS_PER_TOKEN

            table_rows.append([
                model,
                format_number(r['turns_with_thinking']),
                format_number(chars),
                format_number(avg_chars),
                format_tokens(tokens),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # Thinking by project
    cursor = conn.execute(f"""
        SELECT
            s.project_display,
            SUM(t.thinking_chars) as thinking_chars,
            COUNT(CASE WHEN t.thinking_chars > 0 THEN 1 END) as turns_with_thinking,
            AVG(CASE WHEN t.thinking_chars > 0 THEN t.thinking_chars END) as avg_thinking_chars
        FROM turns t
        JOIN sessions s ON s.session_id = t.session_id
        WHERE 1=1 {date_filter}
        GROUP BY s.project_display
        HAVING turns_with_thinking > 0
        ORDER BY thinking_chars DESC
        LIMIT 10
    """, params)

    project_rows = cursor.fetchall()

    if project_rows:
        lines.append(bold("THINKING BY PROJECT", color_enabled))
        headers = ['Project', 'Thinking Chars', 'Turns', 'Avg Chars/Turn']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        max_chars = max(r['thinking_chars'] or 0 for r in project_rows)

        for r in project_rows:
            project = r['project_display'] or 'Unknown'
            if len(project) > 35:
                project = project[:32] + '...'
            chars = r['thinking_chars'] or 0
            avg_chars = r['avg_thinking_chars'] or 0

            table_rows.append([
                project,
                format_number(chars),
                format_number(r['turns_with_thinking']),
                format_number(avg_chars),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # Daily thinking trend (last 14 days)
    cursor = conn.execute(f"""
        SELECT
            date(t.timestamp) as date,
            SUM(t.thinking_chars) as thinking_chars,
            COUNT(CASE WHEN t.thinking_chars > 0 THEN 1 END) as turns_with_thinking,
            AVG(CASE WHEN t.thinking_chars > 0 THEN t.thinking_chars END) as avg_thinking_chars
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY date(t.timestamp)
        HAVING turns_with_thinking > 0
        ORDER BY date DESC
        LIMIT 14
    """, params)

    daily_rows = cursor.fetchall()

    if daily_rows:
        lines.append(bold("DAILY THINKING TREND", color_enabled))
        headers = ['Date', 'Thinking Chars', 'Turns', 'Avg/Turn', 'Bar']
        alignments = ['l', 'r', 'r', 'r', 'l']
        table_rows = []

        max_chars = max(r['thinking_chars'] or 0 for r in daily_rows)

        for r in daily_rows:
            chars = r['thinking_chars'] or 0
            avg_chars = r['avg_thinking_chars'] or 0
            bar = create_bar(chars, max_chars, width=15)

            table_rows.append([
                r['date'],
                format_number(chars),
                format_number(r['turns_with_thinking']),
                format_number(avg_chars),
                bar,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # Thinking impact on errors
    _append_thinking_impact(conn, lines, date_filter, params, color_enabled)

    return '\n'.join(lines)


def _append_thinking_impact(
    conn: sqlite3.Connection,
    lines: list,
    date_filter: str,
    params: list,
    color_enabled: bool
) -> None:
    """Append thinking impact on error rates section."""
    tc_date_filter = date_filter.replace("t.timestamp", "tc.timestamp")

    cursor = conn.execute(f"""
        SELECT
            CASE WHEN has_thinking > 0 THEN 1 ELSE 0 END as uses_thinking,
            COUNT(*) as total_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls tc
        JOIN (
            SELECT
                session_id,
                SUM(CASE WHEN thinking_chars > 0 THEN 1 ELSE 0 END) as has_thinking
            FROM turns
            GROUP BY session_id
        ) ts ON ts.session_id = tc.session_id
        WHERE 1=1 {tc_date_filter}
        GROUP BY uses_thinking
    """, params)

    impact_rows = cursor.fetchall()

    if not impact_rows:
        return

    lines.append(bold("THINKING IMPACT ON ERRORS", color_enabled))
    lines.append("-" * 40)

    thinking_errors = 0
    thinking_total = 0
    no_thinking_errors = 0
    no_thinking_total = 0

    for r in impact_rows:
        if r['uses_thinking']:
            thinking_errors = r['errors'] or 0
            thinking_total = r['total_calls'] or 0
        else:
            no_thinking_errors = r['errors'] or 0
            no_thinking_total = r['total_calls'] or 0

    thinking_rate = (thinking_errors / thinking_total * 100) if thinking_total > 0 else 0
    no_thinking_rate = (no_thinking_errors / no_thinking_total * 100) if no_thinking_total > 0 else 0

    thinking_color = Colors.GREEN if thinking_rate < no_thinking_rate else Colors.RED
    no_thinking_color = Colors.GREEN if no_thinking_rate < thinking_rate else Colors.RED

    lines.append(f"With thinking:        {format_number(thinking_total):>8} calls, "
                 f"{colorize(format_percentage(thinking_rate, 1), thinking_color, color_enabled)} error rate")
    lines.append(f"Without thinking:     {format_number(no_thinking_total):>8} calls, "
                 f"{colorize(format_percentage(no_thinking_rate, 1), no_thinking_color, color_enabled)} error rate")

    if thinking_total > 0 and no_thinking_total > 0:
        if no_thinking_rate > 0:
            reduction = ((no_thinking_rate - thinking_rate) / no_thinking_rate) * 100
            if reduction > 0:
                lines.append(f"Error reduction:      {colorize(format_percentage(reduction, 1), Colors.GREEN, color_enabled)}")
            else:
                lines.append(f"Error increase:       {colorize(format_percentage(abs(reduction), 1), Colors.RED, color_enabled)}")
