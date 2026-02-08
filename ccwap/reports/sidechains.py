"""
Sidechain/branching analysis report for CCWAP.

Generates the --sidechains view analyzing conversation branching patterns.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, bold, colorize, Colors, create_bar
)


def generate_sidechains(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate sidechain/branching analysis report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("SIDECHAIN/BRANCHING ANALYSIS", color_enabled))

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

    # ── Section 1: SIDECHAIN OVERVIEW ────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            COUNT(*) as total_turns,
            SUM(CASE WHEN t.is_sidechain = 1 THEN 1 ELSE 0 END) as sidechain_turns,
            SUM(t.cost) as total_cost,
            SUM(CASE WHEN t.is_sidechain = 1 THEN t.cost ELSE 0 END) as sidechain_cost
        FROM turns t
        WHERE 1=1 {date_filter}
    """, params)

    summary = cursor.fetchone()
    total_turns = summary['total_turns'] or 0
    sidechain_turns = summary['sidechain_turns'] or 0
    total_cost = summary['total_cost'] or 0
    sidechain_cost = summary['sidechain_cost'] or 0

    if total_turns == 0:
        return lines[0] + "\n\nNo data found."

    sidechain_pct = (sidechain_turns / total_turns * 100) if total_turns > 0 else 0
    sidechain_cost_pct = (sidechain_cost / total_cost * 100) if total_cost > 0 else 0

    if sidechain_pct < 20:
        pct_color = Colors.GREEN
    elif sidechain_pct < 40:
        pct_color = Colors.YELLOW
    else:
        pct_color = Colors.RED

    lines.append(bold("SIDECHAIN OVERVIEW", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Total turns:          {format_number(total_turns)}")
    lines.append(f"Sidechain turns:      {format_number(sidechain_turns)}")
    lines.append(f"Sidechain %:          {colorize(format_percentage(sidechain_pct, 1), pct_color, color_enabled)}")
    lines.append(f"Sidechain cost:       {format_currency(sidechain_cost)}")
    lines.append(f"Sidechain cost %:     {format_percentage(sidechain_cost_pct, 1)}")
    lines.append("")

    # ── Section 2: MAIN PATH vs SIDECHAIN COMPARISON ─────────────

    cursor = conn.execute(f"""
        SELECT
            CASE WHEN t.is_sidechain = 1 THEN 'Sidechain' ELSE 'Main Path' END as path_type,
            COUNT(*) as turns,
            SUM(t.input_tokens + t.output_tokens + t.cache_read_tokens + t.cache_write_tokens) as total_tokens,
            SUM(t.cost) as total_cost,
            AVG(t.input_tokens + t.output_tokens + t.cache_read_tokens + t.cache_write_tokens) as avg_tokens,
            AVG(t.cost) as avg_cost
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY CASE WHEN t.is_sidechain = 1 THEN 'Sidechain' ELSE 'Main Path' END
        ORDER BY path_type DESC
    """, params)

    comparison_rows = cursor.fetchall()

    if comparison_rows:
        lines.append(bold("MAIN PATH vs SIDECHAIN COMPARISON", color_enabled))
        headers = ['Path', 'Turns', 'Total Tokens', 'Total Cost', 'Avg Tokens/Turn', 'Avg Cost/Turn']
        alignments = ['l', 'r', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in comparison_rows:
            table_rows.append([
                r['path_type'],
                format_number(r['turns'] or 0),
                format_tokens(r['total_tokens'] or 0),
                format_currency(r['total_cost'] or 0),
                format_tokens(int(r['avg_tokens'] or 0)),
                format_currency(r['avg_cost'] or 0),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── Section 3: SIDECHAIN USAGE BY MODEL ──────────────────────

    cursor = conn.execute(f"""
        SELECT
            t.model,
            COUNT(*) as total_turns,
            SUM(CASE WHEN t.is_sidechain = 1 THEN 1 ELSE 0 END) as sidechain_turns,
            SUM(CASE WHEN t.is_sidechain = 1 THEN t.cost ELSE 0 END) as sidechain_cost
        FROM turns t
        WHERE t.model IS NOT NULL {date_filter}
        GROUP BY t.model
        ORDER BY sidechain_cost DESC
    """, params)

    model_rows = cursor.fetchall()

    if model_rows:
        lines.append(bold("SIDECHAIN USAGE BY MODEL", color_enabled))
        headers = ['Model', 'Total Turns', 'Sidechain Turns', 'Sidechain %', 'Sidechain Cost']
        alignments = ['l', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in model_rows:
            model = r['model'] or 'Unknown'
            if len(model) > 30:
                model = model[:27] + '...'
            total = r['total_turns'] or 0
            sc_turns = r['sidechain_turns'] or 0
            sc_pct = (sc_turns / total * 100) if total > 0 else 0
            sc_cost = r['sidechain_cost'] or 0

            pct_str = format_percentage(sc_pct, 1)
            if sc_pct >= 40:
                pct_str = colorize(pct_str, Colors.RED, color_enabled)
            elif sc_pct >= 20:
                pct_str = colorize(pct_str, Colors.YELLOW, color_enabled)

            table_rows.append([
                model,
                format_number(total),
                format_number(sc_turns),
                pct_str,
                format_currency(sc_cost),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── Section 4: SIDECHAIN USAGE BY PROJECT ────────────────────

    cursor = conn.execute(f"""
        SELECT
            s.project_display,
            COUNT(*) as total_turns,
            SUM(CASE WHEN t.is_sidechain = 1 THEN 1 ELSE 0 END) as sidechain_turns,
            SUM(CASE WHEN t.is_sidechain = 1 THEN t.cost ELSE 0 END) as sidechain_cost
        FROM turns t
        JOIN sessions s ON s.session_id = t.session_id
        WHERE 1=1 {date_filter}
        GROUP BY s.project_display
        ORDER BY sidechain_cost DESC
        LIMIT 10
    """, params)

    project_rows = cursor.fetchall()

    if project_rows:
        lines.append(bold("SIDECHAIN USAGE BY PROJECT (Top 10)", color_enabled))
        headers = ['Project', 'Total Turns', 'Sidechain Turns', 'Sidechain %', 'Sidechain Cost']
        alignments = ['l', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in project_rows:
            project = r['project_display'] or 'Unknown'
            if len(project) > 35:
                project = project[:32] + '...'
            total = r['total_turns'] or 0
            sc_turns = r['sidechain_turns'] or 0
            sc_pct = (sc_turns / total * 100) if total > 0 else 0
            sc_cost = r['sidechain_cost'] or 0

            pct_str = format_percentage(sc_pct, 1)
            if sc_pct >= 40:
                pct_str = colorize(pct_str, Colors.RED, color_enabled)
            elif sc_pct >= 20:
                pct_str = colorize(pct_str, Colors.YELLOW, color_enabled)

            table_rows.append([
                project,
                format_number(total),
                format_number(sc_turns),
                pct_str,
                format_currency(sc_cost),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── Section 5: SIDECHAIN OVERHEAD BY SESSION ─────────────────

    cursor = conn.execute(f"""
        SELECT
            t.session_id,
            s.project_display,
            SUM(t.cost) as total_cost,
            SUM(CASE WHEN t.is_sidechain = 1 THEN t.cost ELSE 0 END) as sidechain_cost,
            COUNT(*) as total_turns,
            SUM(CASE WHEN t.is_sidechain = 1 THEN 1 ELSE 0 END) as sidechain_turns
        FROM turns t
        JOIN sessions s ON s.session_id = t.session_id
        WHERE 1=1 {date_filter}
        GROUP BY t.session_id
        HAVING sidechain_cost > 0
        ORDER BY sidechain_cost DESC
        LIMIT 10
    """, params)

    session_rows = cursor.fetchall()

    if session_rows:
        lines.append(bold("SIDECHAIN OVERHEAD BY SESSION (Top 10)", color_enabled))
        headers = ['Session', 'Project', 'Total Cost', 'Sidechain Cost', 'Sidechain %']
        alignments = ['l', 'l', 'r', 'r', 'r']
        table_rows = []

        for r in session_rows:
            session_id = r['session_id'][:8]
            project = r['project_display'] or 'Unknown'
            if len(project) > 25:
                project = project[:22] + '...'
            t_cost = r['total_cost'] or 0
            sc_cost = r['sidechain_cost'] or 0
            sc_pct = (sc_cost / t_cost * 100) if t_cost > 0 else 0

            pct_str = format_percentage(sc_pct, 1)
            if sc_pct >= 40:
                pct_str = colorize(pct_str, Colors.RED, color_enabled)
            elif sc_pct >= 20:
                pct_str = colorize(pct_str, Colors.YELLOW, color_enabled)

            table_rows.append([
                session_id,
                project,
                format_currency(t_cost),
                format_currency(sc_cost),
                pct_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── Section 6: DAILY SIDECHAIN TREND ─────────────────────────

    cursor = conn.execute(f"""
        SELECT
            date(t.timestamp) as date,
            COUNT(*) as total_turns,
            SUM(CASE WHEN t.is_sidechain = 1 THEN 1 ELSE 0 END) as sidechain_turns
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY date(t.timestamp)
        ORDER BY date DESC
        LIMIT 14
    """, params)

    trend_rows = cursor.fetchall()

    if trend_rows:
        lines.append(bold("DAILY SIDECHAIN TREND (Last 14 Days)", color_enabled))
        headers = ['Date', 'Total Turns', 'Sidechain Turns', 'Sidechain %', 'Bar']
        alignments = ['l', 'r', 'r', 'r', 'l']
        table_rows = []

        max_pct = 0
        for r in trend_rows:
            total = r['total_turns'] or 0
            sc = r['sidechain_turns'] or 0
            pct = (sc / total * 100) if total > 0 else 0
            if pct > max_pct:
                max_pct = pct

        for r in trend_rows:
            date_str = r['date']
            total = r['total_turns'] or 0
            sc = r['sidechain_turns'] or 0
            pct = (sc / total * 100) if total > 0 else 0

            pct_str = format_percentage(pct, 1)
            if pct >= 40:
                pct_str = colorize(pct_str, Colors.RED, color_enabled)
            elif pct >= 20:
                pct_str = colorize(pct_str, Colors.YELLOW, color_enabled)

            bar = create_bar(pct, max_pct, width=15) if max_pct > 0 else create_bar(0, 1, width=15)

            table_rows.append([
                date_str,
                format_number(total),
                format_number(sc),
                pct_str,
                bar,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))

    return '\n'.join(lines)
