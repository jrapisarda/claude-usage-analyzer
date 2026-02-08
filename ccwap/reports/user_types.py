"""
User type breakdown report for CCWAP.

Generates the --user-types view analyzing human vs AI-generated turns.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, bold, colorize, Colors, create_bar
)


def generate_user_types(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate user type breakdown report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("USER TYPE BREAKDOWN", color_enabled))

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

    # ── Section 1: User Type Distribution ────────────────────────
    cursor = conn.execute(f"""
        SELECT
            COALESCE(t.user_type, 'unknown') as type_label,
            COUNT(*) as turns,
            SUM(t.cost) as cost
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY COALESCE(t.user_type, 'unknown')
        ORDER BY turns DESC
    """, params)

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo data found."

    total_turns = sum(r['turns'] for r in rows)
    total_cost = sum(r['cost'] or 0 for r in rows)
    max_turns = max(r['turns'] for r in rows)

    lines.append(bold("USER TYPE DISTRIBUTION", color_enabled))
    lines.append("")

    headers = ['Type', 'Turns', '% of Total', 'Total Cost', 'Avg Cost/Turn', 'Bar']
    alignments = ['l', 'r', 'r', 'r', 'r', 'l']
    table_rows = []

    for r in rows:
        type_label = r['type_label']
        turns = r['turns']
        cost = r['cost'] or 0
        pct = (turns / total_turns * 100) if total_turns > 0 else 0
        avg_cost = (cost / turns) if turns > 0 else 0
        bar = create_bar(turns, max_turns, width=15)

        table_rows.append([
            type_label,
            format_number(turns),
            format_percentage(pct, 1),
            format_currency(cost),
            format_currency(avg_cost),
            bar,
        ])

    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_number(total_turns), color_enabled),
        bold('100.0%', color_enabled),
        bold(format_currency(total_cost), color_enabled),
        bold(format_currency(total_cost / total_turns if total_turns > 0 else 0), color_enabled),
        '',
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # ── Section 2: Human vs AI-Generated Turns ───────────────────
    lines.append("")
    lines.append(bold("HUMAN vs AI-GENERATED TURNS", color_enabled))
    lines.append("-" * 40)

    cursor = conn.execute(f"""
        SELECT
            CASE WHEN t.user_type = 'external' THEN 'human'
                 WHEN t.user_type = 'internal' THEN 'ai'
                 ELSE 'other' END as category,
            COUNT(*) as turns,
            SUM(t.input_tokens + t.output_tokens) as total_tokens,
            SUM(t.cost) as cost
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY category
    """, params)

    compare_rows = cursor.fetchall()

    human_turns = 0
    human_tokens = 0
    human_cost = 0.0
    ai_turns = 0
    ai_tokens = 0
    ai_cost = 0.0

    for r in compare_rows:
        if r['category'] == 'human':
            human_turns = r['turns']
            human_tokens = r['total_tokens'] or 0
            human_cost = r['cost'] or 0
        elif r['category'] == 'ai':
            ai_turns = r['turns']
            ai_tokens = r['total_tokens'] or 0
            ai_cost = r['cost'] or 0

    human_avg_tokens = (human_tokens / human_turns) if human_turns > 0 else 0
    ai_avg_tokens = (ai_tokens / ai_turns) if ai_turns > 0 else 0
    human_avg_cost = (human_cost / human_turns) if human_turns > 0 else 0
    ai_avg_cost = (ai_cost / ai_turns) if ai_turns > 0 else 0

    lines.append(f"{'':30} {'Human':>12}  {'AI-Generated':>12}")
    lines.append(f"{'Total turns':30} {format_number(human_turns):>12}  {format_number(ai_turns):>12}")
    lines.append(f"{'Total tokens':30} {format_tokens(human_tokens):>12}  {format_tokens(ai_tokens):>12}")
    lines.append(f"{'Total cost':30} {format_currency(human_cost):>12}  {format_currency(ai_cost):>12}")
    lines.append(f"{'Avg tokens/turn':30} {format_tokens(int(human_avg_tokens)):>12}  {format_tokens(int(ai_avg_tokens)):>12}")
    lines.append(f"{'Avg cost/turn':30} {format_currency(human_avg_cost):>12}  {format_currency(ai_avg_cost):>12}")

    if human_avg_cost > 0 and ai_avg_cost > 0:
        if ai_avg_cost > human_avg_cost:
            ratio = ai_avg_cost / human_avg_cost
            lines.append("")
            lines.append(colorize(
                f"AI-generated turns are {ratio:.1f}x more expensive per turn than human turns.",
                Colors.YELLOW, color_enabled
            ))
        else:
            ratio = human_avg_cost / ai_avg_cost
            lines.append("")
            lines.append(colorize(
                f"Human turns are {ratio:.1f}x more expensive per turn than AI-generated turns.",
                Colors.YELLOW, color_enabled
            ))

    # ── Section 3: User Type by Project (Top 10) ─────────────────
    lines.append("")
    lines.append(bold("USER TYPE BY PROJECT", color_enabled))
    lines.append("")

    cursor = conn.execute(f"""
        SELECT
            s.project_display,
            COUNT(CASE WHEN t.user_type = 'external' THEN 1 END) as human_turns,
            COUNT(CASE WHEN t.user_type = 'internal' THEN 1 END) as ai_turns,
            COUNT(*) as total_turns,
            SUM(t.cost) as cost
        FROM turns t
        JOIN sessions s ON s.session_id = t.session_id
        WHERE 1=1 {date_filter}
        GROUP BY s.project_display
        ORDER BY cost DESC
        LIMIT 10
    """, params)

    project_rows = cursor.fetchall()

    if project_rows:
        headers = ['Project', 'Human Turns', 'AI Turns', 'AI %', 'Total Cost']
        alignments = ['l', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in project_rows:
            project = r['project_display'] or 'Unknown'
            if len(project) > 35:
                project = project[:32] + '...'

            h_turns = r['human_turns'] or 0
            a_turns = r['ai_turns'] or 0
            t_turns = r['total_turns'] or 0
            cost = r['cost'] or 0
            ai_pct = (a_turns / t_turns * 100) if t_turns > 0 else 0

            ai_pct_str = format_percentage(ai_pct, 1)
            if ai_pct >= 50:
                ai_pct_str = colorize(ai_pct_str, Colors.CYAN, color_enabled)

            table_rows.append([
                project,
                format_number(h_turns),
                format_number(a_turns),
                ai_pct_str,
                format_currency(cost),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
    else:
        lines.append("No project data available.")

    # ── Section 4: User Type Cost Trend (Last 14 Days) ───────────
    lines.append("")
    lines.append(bold("USER TYPE COST TREND (LAST 14 DAYS)", color_enabled))
    lines.append("")

    cursor = conn.execute(f"""
        SELECT
            date(t.timestamp) as date,
            SUM(CASE WHEN t.user_type = 'external' THEN t.cost ELSE 0 END) as human_cost,
            SUM(CASE WHEN t.user_type = 'internal' THEN t.cost ELSE 0 END) as ai_cost,
            SUM(t.cost) as total_cost
        FROM turns t
        WHERE 1=1
            AND date(t.timestamp) >= date('now', '-14 days')
            {date_filter}
        GROUP BY date(t.timestamp)
        ORDER BY date DESC
    """, params)

    trend_rows = cursor.fetchall()

    if trend_rows:
        headers = ['Date', 'Human Cost', 'AI Cost', 'AI Cost %']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in trend_rows:
            h_cost = r['human_cost'] or 0
            a_cost = r['ai_cost'] or 0
            t_cost = r['total_cost'] or 0
            ai_cost_pct = (a_cost / t_cost * 100) if t_cost > 0 else 0

            table_rows.append([
                r['date'],
                format_currency(h_cost),
                format_currency(a_cost),
                format_percentage(ai_cost_pct, 1),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
    else:
        lines.append("No trend data available.")

    # ── Section 5: Autonomy Metrics ──────────────────────────────
    lines.append("")
    lines.append(bold("AUTONOMY METRICS", color_enabled))
    lines.append("-" * 40)

    total_all_turns = human_turns + ai_turns
    autonomy_ratio = (ai_turns / total_all_turns * 100) if total_all_turns > 0 else 0
    ai_cost_pct = (ai_cost / total_cost * 100) if total_cost > 0 else 0

    lines.append(f"Total human turns:    {format_number(human_turns)}")
    lines.append(f"Total AI turns:       {format_number(ai_turns)}")

    autonomy_str = format_percentage(autonomy_ratio, 1)
    if autonomy_ratio >= 50:
        autonomy_str = colorize(autonomy_str, Colors.CYAN, color_enabled)
    lines.append(f"Autonomy ratio:       {autonomy_str}")

    lines.append(f"Cost from AI:         {format_currency(ai_cost)}")

    ai_cost_pct_str = format_percentage(ai_cost_pct, 1)
    if ai_cost_pct >= 50:
        ai_cost_pct_str = colorize(ai_cost_pct_str, Colors.CYAN, color_enabled)
    lines.append(f"AI cost % of total:   {ai_cost_pct_str}")

    if autonomy_ratio >= 50:
        lines.append("")
        lines.append(colorize(
            "High autonomy ratio: most work is agent-driven.",
            Colors.CYAN, color_enabled
        ))

    return '\n'.join(lines)
