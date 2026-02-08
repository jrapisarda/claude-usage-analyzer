"""
Branch-aware analytics report for CCWAP.

Generates the --branches view with per-branch cost and efficiency analysis.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, bold, colorize, Colors, create_bar
)


def generate_branches(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate branch-aware analytics report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("BRANCH ANALYTICS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build date filter
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(s.first_timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(s.first_timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # ── SUMMARY ──────────────────────────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            COUNT(DISTINCT COALESCE(s.git_branch, 'unknown')) as unique_branches,
            COUNT(DISTINCT s.session_id) as total_sessions
        FROM sessions s
        WHERE 1=1 {date_filter}
    """, params)

    summary = cursor.fetchone()

    if not summary or summary['total_sessions'] == 0:
        return lines[0] + "\n\nNo branch data found."

    # Branch with most sessions
    cursor = conn.execute(f"""
        SELECT
            COALESCE(s.git_branch, 'unknown') as branch,
            COUNT(DISTINCT s.session_id) as sessions
        FROM sessions s
        WHERE 1=1 {date_filter}
        GROUP BY COALESCE(s.git_branch, 'unknown')
        ORDER BY sessions DESC
        LIMIT 1
    """, params)

    top_branch = cursor.fetchone()

    lines.append(bold("SUMMARY", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Unique branches:      {format_number(summary['unique_branches'])}")
    lines.append(f"Total sessions:       {format_number(summary['total_sessions'])}")
    if top_branch:
        lines.append(f"Most active branch:   {top_branch['branch']} ({format_number(top_branch['sessions'])} sessions)")
    lines.append("")

    # ── COST BY BRANCH (Top 15) ──────────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            COALESCE(s.git_branch, 'unknown') as branch,
            COUNT(DISTINCT s.session_id) as sessions,
            COUNT(t.rowid) as turns,
            SUM(t.cost) as cost
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE 1=1 {date_filter}
        GROUP BY COALESCE(s.git_branch, 'unknown')
        ORDER BY cost DESC
        LIMIT 15
    """, params)

    cost_rows = cursor.fetchall()

    if cost_rows:
        lines.append(bold("COST BY BRANCH (Top 15)", color_enabled))
        lines.append("")

        max_cost = max(r['cost'] or 0 for r in cost_rows)

        headers = ['Branch', 'Sessions', 'Turns', 'Total Cost', 'Avg Cost/Sess', 'Bar']
        alignments = ['l', 'r', 'r', 'r', 'r', 'l']
        table_rows = []

        for r in cost_rows:
            branch = r['branch']
            if len(branch) > 25:
                branch = branch[:22] + '...'

            sessions = r['sessions'] or 0
            cost = r['cost'] or 0
            avg_cost = cost / sessions if sessions > 0 else 0

            bar = create_bar(cost, max_cost, width=15)

            table_rows.append([
                branch,
                format_number(sessions),
                format_number(r['turns'] or 0),
                format_currency(cost),
                format_currency(avg_cost),
                bar,
            ])

        # Totals row
        total_sessions = sum(r['sessions'] or 0 for r in cost_rows)
        total_turns = sum(r['turns'] or 0 for r in cost_rows)
        total_cost = sum(r['cost'] or 0 for r in cost_rows)

        table_rows.append([
            bold('TOTAL', color_enabled),
            bold(format_number(total_sessions), color_enabled),
            bold(format_number(total_turns), color_enabled),
            bold(format_currency(total_cost), color_enabled),
            bold(format_currency(total_cost / total_sessions if total_sessions > 0 else 0), color_enabled),
            '',
        ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── BRANCH EFFICIENCY (Top 15) ───────────────────────────────────

    # Use subqueries to avoid cross-product between turns and tool_calls
    cursor = conn.execute(f"""
        SELECT
            tc_stats.branch,
            tc_stats.loc_written,
            COALESCE(turn_stats.cost, 0) as cost,
            tc_stats.tool_calls,
            tc_stats.errors
        FROM (
            SELECT
                COALESCE(s.git_branch, 'unknown') as branch,
                SUM(tc.loc_written) as loc_written,
                COUNT(tc.rowid) as tool_calls,
                SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors
            FROM sessions s
            JOIN tool_calls tc ON tc.session_id = s.session_id
            WHERE 1=1 {date_filter}
            GROUP BY COALESCE(s.git_branch, 'unknown')
        ) tc_stats
        LEFT JOIN (
            SELECT
                COALESCE(s.git_branch, 'unknown') as branch,
                SUM(t.cost) as cost
            FROM sessions s
            LEFT JOIN turns t ON t.session_id = s.session_id
            WHERE 1=1 {date_filter}
            GROUP BY COALESCE(s.git_branch, 'unknown')
        ) turn_stats ON turn_stats.branch = tc_stats.branch
        ORDER BY tc_stats.loc_written DESC
        LIMIT 15
    """, params + params)

    eff_rows = cursor.fetchall()

    if eff_rows:
        lines.append(bold("BRANCH EFFICIENCY (Top 15)", color_enabled))
        lines.append("")

        headers = ['Branch', 'LOC Written', 'Cost/KLOC', 'Tool Calls', 'Error Rate']
        alignments = ['l', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in eff_rows:
            branch = r['branch']
            if len(branch) > 25:
                branch = branch[:22] + '...'

            loc = r['loc_written'] or 0
            cost = r['cost'] or 0
            tool_calls = r['tool_calls'] or 0
            errors = r['errors'] or 0

            cost_per_kloc = cost / (loc / 1000) if loc > 0 else 0
            error_rate = (errors / tool_calls * 100) if tool_calls > 0 else 0

            error_str = format_percentage(error_rate, 1)
            if error_rate > 10:
                error_str = colorize(error_str, Colors.RED, color_enabled)

            table_rows.append([
                branch,
                format_number(loc),
                format_currency(cost_per_kloc),
                format_number(tool_calls),
                error_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── MAIN vs FEATURE BRANCHES ─────────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            CASE
                WHEN LOWER(COALESCE(s.git_branch, '')) IN ('main', 'master')
                     OR LOWER(COALESCE(s.git_branch, '')) LIKE '%%main%%'
                     OR LOWER(COALESCE(s.git_branch, '')) LIKE '%%master%%'
                THEN 'main/master'
                ELSE 'feature'
            END as branch_type,
            COUNT(DISTINCT s.session_id) as sessions,
            COUNT(t.rowid) as turns,
            SUM(t.cost) as cost
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE 1=1 {date_filter}
        GROUP BY branch_type
    """, params)

    type_rows = cursor.fetchall()

    if type_rows:
        # Get error rates per branch type
        type_errors = {}
        cursor = conn.execute(f"""
            SELECT
                CASE
                    WHEN LOWER(COALESCE(s.git_branch, '')) IN ('main', 'master')
                         OR LOWER(COALESCE(s.git_branch, '')) LIKE '%%main%%'
                         OR LOWER(COALESCE(s.git_branch, '')) LIKE '%%master%%'
                    THEN 'main/master'
                    ELSE 'feature'
                END as branch_type,
                COUNT(tc.rowid) as tool_calls,
                SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors
            FROM sessions s
            JOIN tool_calls tc ON tc.session_id = s.session_id
            WHERE 1=1 {date_filter}
            GROUP BY branch_type
        """, params)

        for row in cursor.fetchall():
            tc = row['tool_calls'] or 0
            err = row['errors'] or 0
            type_errors[row['branch_type']] = (err / tc * 100) if tc > 0 else 0

        lines.append(bold("MAIN vs FEATURE BRANCHES", color_enabled))
        lines.append("")

        headers = ['Branch Type', 'Sessions', 'Turns', 'Total Cost', 'Avg Cost/Sess', 'Error Rate']
        alignments = ['l', 'r', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in type_rows:
            bt = r['branch_type']
            sessions = r['sessions'] or 0
            cost = r['cost'] or 0
            avg_cost = cost / sessions if sessions > 0 else 0
            error_rate = type_errors.get(bt, 0)

            error_str = format_percentage(error_rate, 1)
            if error_rate > 10:
                error_str = colorize(error_str, Colors.RED, color_enabled)

            table_rows.append([
                bt,
                format_number(sessions),
                format_number(r['turns'] or 0),
                format_currency(cost),
                format_currency(avg_cost),
                error_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── BRANCH ACTIVITY TREND (Last 14 days) ─────────────────────────

    cursor = conn.execute(f"""
        SELECT
            date(s.first_timestamp) as date,
            COUNT(DISTINCT COALESCE(s.git_branch, 'unknown')) as unique_branches,
            COUNT(DISTINCT s.session_id) as sessions,
            SUM(t.cost) as cost
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE date(s.first_timestamp) >= date('now', '-14 days') {date_filter}
        GROUP BY date(s.first_timestamp)
        ORDER BY date DESC
    """, params)

    trend_rows = cursor.fetchall()

    if trend_rows:
        lines.append(bold("BRANCH ACTIVITY TREND (Last 14 days)", color_enabled))
        lines.append("")

        headers = ['Date', 'Branches', 'Sessions', 'Cost']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in trend_rows:
            table_rows.append([
                r['date'],
                format_number(r['unique_branches'] or 0),
                format_number(r['sessions'] or 0),
                format_currency(r['cost'] or 0),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── MOST ACTIVE BRANCHES THIS WEEK ───────────────────────────────

    # Use subqueries to avoid cross-product between turns and tool_calls
    cursor = conn.execute(f"""
        SELECT
            sess_stats.branch,
            sess_stats.sessions,
            COALESCE(turn_stats.cost, 0) as cost,
            COALESCE(tc_stats.loc_written, 0) as loc_written
        FROM (
            SELECT
                COALESCE(s.git_branch, 'unknown') as branch,
                COUNT(DISTINCT s.session_id) as sessions
            FROM sessions s
            WHERE date(s.first_timestamp) >= date('now', '-7 days') {date_filter}
            GROUP BY COALESCE(s.git_branch, 'unknown')
        ) sess_stats
        LEFT JOIN (
            SELECT
                COALESCE(s.git_branch, 'unknown') as branch,
                SUM(t.cost) as cost
            FROM sessions s
            LEFT JOIN turns t ON t.session_id = s.session_id
            WHERE date(s.first_timestamp) >= date('now', '-7 days') {date_filter}
            GROUP BY COALESCE(s.git_branch, 'unknown')
        ) turn_stats ON turn_stats.branch = sess_stats.branch
        LEFT JOIN (
            SELECT
                COALESCE(s.git_branch, 'unknown') as branch,
                SUM(tc.loc_written) as loc_written
            FROM sessions s
            JOIN tool_calls tc ON tc.session_id = s.session_id
            WHERE date(s.first_timestamp) >= date('now', '-7 days') {date_filter}
            GROUP BY COALESCE(s.git_branch, 'unknown')
        ) tc_stats ON tc_stats.branch = sess_stats.branch
        ORDER BY sess_stats.sessions DESC
        LIMIT 10
    """, params + params + params)

    week_rows = cursor.fetchall()

    if week_rows:
        lines.append(bold("MOST ACTIVE BRANCHES THIS WEEK", color_enabled))
        lines.append("")

        headers = ['Branch', 'Sessions', 'Cost', 'LOC']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in week_rows:
            branch = r['branch']
            if len(branch) > 30:
                branch = branch[:27] + '...'

            table_rows.append([
                branch,
                format_number(r['sessions'] or 0),
                format_currency(r['cost'] or 0),
                format_number(r['loc_written'] or 0),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))

    return '\n'.join(lines)
