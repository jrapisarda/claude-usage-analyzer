"""
Truncation analysis report for CCWAP.

Generates the --truncation view analyzing stop_reason patterns.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, bold, colorize, Colors, create_bar
)


def generate_truncation(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate truncation analysis report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("TRUNCATION ANALYSIS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build query with optional date filters
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(t.timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(t.timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # ── STOP REASON DISTRIBUTION ──────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            COALESCE(t.stop_reason, 'null') as reason,
            COUNT(*) as count
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY COALESCE(t.stop_reason, 'null')
        ORDER BY count DESC
    """, params)

    reason_rows = cursor.fetchall()

    if not reason_rows:
        return lines[0] + "\n\nNo turn data found."

    total_turns = sum(r['count'] for r in reason_rows)
    max_count = max(r['count'] for r in reason_rows)

    lines.append(bold("STOP REASON DISTRIBUTION", color_enabled))
    lines.append("-" * 40)

    reason_labels = {
        'end_turn': 'end_turn (completed normally)',
        'max_tokens': 'max_tokens (truncated!)',
        'tool_use': 'tool_use (paused for tool)',
        'null': 'null/other',
    }

    for r in reason_rows:
        reason = r['reason']
        count = r['count']
        pct = (count / total_turns * 100) if total_turns > 0 else 0
        bar = create_bar(count, max_count, width=20)
        label = reason_labels.get(reason, reason)

        line = f"{label:30} {format_number(count):>7} ({format_percentage(pct, 1):>6}) {bar}"
        if reason == 'max_tokens':
            line = colorize(line, Colors.RED, color_enabled)
        lines.append(line)

    lines.append("")

    # ── TRUNCATION RATE ───────────────────────────────────────

    truncated_count = 0
    for r in reason_rows:
        if r['reason'] == 'max_tokens':
            truncated_count = r['count']
            break

    truncation_rate = (truncated_count / total_turns * 100) if total_turns > 0 else 0

    lines.append(bold("TRUNCATION RATE", color_enabled))
    lines.append("-" * 40)

    if truncation_rate < 5:
        rate_color = Colors.GREEN
    elif truncation_rate < 10:
        rate_color = Colors.YELLOW
    else:
        rate_color = Colors.RED

    rate_str = colorize(format_percentage(truncation_rate, 1), rate_color, color_enabled)
    lines.append(f"Overall truncation rate:  {rate_str}")
    lines.append(f"Truncated turns:          {format_number(truncated_count)} / {format_number(total_turns)}")
    lines.append("")

    # ── TRUNCATION BY MODEL ───────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            t.model,
            COUNT(*) as total,
            SUM(CASE WHEN t.stop_reason = 'max_tokens' THEN 1 ELSE 0 END) as truncated
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY t.model
        ORDER BY truncated DESC
    """, params)

    model_rows = cursor.fetchall()

    if model_rows:
        lines.append(bold("TRUNCATION BY MODEL", color_enabled))
        headers = ['Model', 'Total Turns', 'Truncated', 'Rate']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in model_rows:
            model = r['model'] or 'Unknown'
            total = r['total'] or 0
            truncated = r['truncated'] or 0
            rate = (truncated / total * 100) if total > 0 else 0

            rate_str = format_percentage(rate, 1)
            if rate >= 10:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)
            elif rate >= 5:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)

            table_rows.append([
                model,
                format_number(total),
                format_number(truncated),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── TRUNCATION BY PROJECT ─────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            s.project_display,
            COUNT(*) as total,
            SUM(CASE WHEN t.stop_reason = 'max_tokens' THEN 1 ELSE 0 END) as truncated
        FROM turns t
        JOIN sessions s ON s.session_id = t.session_id
        WHERE 1=1 {date_filter}
        GROUP BY s.project_display
        HAVING total >= 10
        ORDER BY (CAST(truncated AS REAL) / total) DESC
        LIMIT 10
    """, params)

    project_rows = cursor.fetchall()

    if project_rows:
        lines.append(bold("TRUNCATION BY PROJECT", color_enabled))
        lines.append("(minimum 10 turns)")
        headers = ['Project', 'Turns', 'Truncated', 'Rate']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in project_rows:
            project = r['project_display'] or 'Unknown'
            if len(project) > 35:
                project = project[:32] + '...'
            total = r['total'] or 0
            truncated = r['truncated'] or 0
            rate = (truncated / total * 100) if total > 0 else 0

            rate_str = format_percentage(rate, 1)
            if rate >= 10:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)
            elif rate >= 5:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)

            table_rows.append([
                project,
                format_number(total),
                format_number(truncated),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── TRUNCATION COST IMPACT ────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            SUM(CASE WHEN t.stop_reason = 'max_tokens' THEN t.cost ELSE 0 END) as truncated_cost,
            SUM(t.cost) as total_cost,
            AVG(CASE WHEN t.stop_reason = 'max_tokens' THEN t.cost END) as avg_truncated_cost,
            AVG(CASE WHEN t.stop_reason != 'max_tokens' OR t.stop_reason IS NULL THEN t.cost END) as avg_normal_cost
        FROM turns t
        WHERE 1=1 {date_filter}
    """, params)

    cost_row = cursor.fetchone()

    if cost_row:
        truncated_cost = cost_row['truncated_cost'] or 0
        total_cost = cost_row['total_cost'] or 0
        avg_truncated_cost = cost_row['avg_truncated_cost'] or 0
        avg_normal_cost = cost_row['avg_normal_cost'] or 0

        lines.append(bold("TRUNCATION COST IMPACT", color_enabled))
        lines.append("-" * 40)
        lines.append(f"Total cost of truncated turns:  {format_currency(truncated_cost)}")

        if total_cost > 0:
            cost_pct = truncated_cost / total_cost * 100
            lines.append(f"Share of total cost:            {format_percentage(cost_pct, 1)}")

        lines.append(f"Avg cost per truncated turn:    {format_currency(avg_truncated_cost)}")
        lines.append(f"Avg cost per normal turn:       {format_currency(avg_normal_cost)}")

        if avg_normal_cost > 0:
            multiplier = avg_truncated_cost / avg_normal_cost
            mult_str = f"{multiplier:.1f}x"
            if multiplier > 1.5:
                mult_str = colorize(mult_str, Colors.RED, color_enabled)
            lines.append(f"Truncated cost multiplier:      {mult_str}")

        lines.append("")

    # ── DAILY TRUNCATION TREND ────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            date(t.timestamp) as date,
            COUNT(*) as total,
            SUM(CASE WHEN t.stop_reason = 'max_tokens' THEN 1 ELSE 0 END) as truncated
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY date(t.timestamp)
        ORDER BY date DESC
        LIMIT 14
    """, params)

    trend_rows = cursor.fetchall()

    if trend_rows:
        lines.append(bold("DAILY TRUNCATION TREND (Last 14 Days)", color_enabled))
        headers = ['Date', 'Total Turns', 'Truncated', 'Rate', 'Bar']
        alignments = ['l', 'r', 'r', 'r', 'l']
        table_rows = []

        max_rate = 0
        for r in trend_rows:
            total = r['total'] or 0
            truncated = r['truncated'] or 0
            rate = (truncated / total * 100) if total > 0 else 0
            if rate > max_rate:
                max_rate = rate

        for r in trend_rows:
            date_str = r['date']
            total = r['total'] or 0
            truncated = r['truncated'] or 0
            rate = (truncated / total * 100) if total > 0 else 0

            rate_str = format_percentage(rate, 1)
            if rate >= 10:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)
            elif rate >= 5:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)

            bar = create_bar(rate, max_rate, width=15) if max_rate > 0 else create_bar(0, 1, width=15)

            table_rows.append([
                date_str,
                format_number(total),
                format_number(truncated),
                rate_str,
                bar,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))

    return '\n'.join(lines)
