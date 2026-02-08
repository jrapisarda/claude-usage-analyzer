"""
CC version impact analysis report for CCWAP.

Generates the --versions view tracking Claude Code version changes.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, format_duration, bold, colorize, Colors, create_bar
)


def generate_versions(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate CC version impact analysis report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("CC VERSION IMPACT ANALYSIS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build date filter on sessions table
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(s.first_timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(s.first_timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # ── Section 1: Version Usage Overview ─────────────────────────
    cursor = conn.execute(f"""
        SELECT
            COALESCE(s.cc_version, 'unknown') as version,
            COUNT(DISTINCT s.session_id) as sessions,
            COUNT(t.rowid) as turns,
            SUM(t.cost) as cost,
            MIN(s.first_timestamp) as first_seen
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE 1=1 {date_filter}
        GROUP BY COALESCE(s.cc_version, 'unknown')
        ORDER BY MIN(s.first_timestamp)
    """, params)

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo version data found."

    lines.append(bold("VERSION USAGE OVERVIEW", color_enabled))
    lines.append("")

    max_cost = max(r['cost'] or 0 for r in rows)

    headers = ['CC Version', 'Sessions', 'Total Turns', 'Total Cost', 'Avg Cost/Session', 'Bar']
    alignments = ['l', 'r', 'r', 'r', 'r', 'l']
    table_rows = []

    for r in rows:
        version = r['version']
        sessions = r['sessions']
        turns = r['turns'] or 0
        cost = r['cost'] or 0
        avg_cost = (cost / sessions) if sessions > 0 else 0
        bar = create_bar(cost, max_cost, width=15)

        table_rows.append([
            version,
            format_number(sessions),
            format_number(turns),
            format_currency(cost),
            format_currency(avg_cost),
            bar,
        ])

    # Totals row
    total_sessions = sum(r['sessions'] for r in rows)
    total_turns = sum(r['turns'] or 0 for r in rows)
    total_cost = sum(r['cost'] or 0 for r in rows)
    avg_total = (total_cost / total_sessions) if total_sessions > 0 else 0

    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_number(total_sessions), color_enabled),
        bold(format_number(total_turns), color_enabled),
        bold(format_currency(total_cost), color_enabled),
        bold(format_currency(avg_total), color_enabled),
        '',
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # ── Section 2: Version Efficiency Comparison ──────────────────
    lines.append("")
    lines.append(bold("VERSION EFFICIENCY COMPARISON", color_enabled))
    lines.append("")

    # Use subqueries to avoid cross-product between turns and tool_calls
    cursor = conn.execute(f"""
        SELECT
            tc_stats.version,
            tc_stats.loc_written,
            COALESCE(turn_stats.cost, 0) as cost,
            tc_stats.tool_calls,
            tc_stats.successes,
            COALESCE(sess_stats.avg_duration, 0) as avg_duration
        FROM (
            SELECT
                COALESCE(s.cc_version, 'unknown') as version,
                SUM(tc.loc_written) as loc_written,
                COUNT(tc.rowid) as tool_calls,
                SUM(CASE WHEN tc.success = 1 THEN 1 ELSE 0 END) as successes,
                MIN(s.first_timestamp) as first_seen
            FROM sessions s
            JOIN tool_calls tc ON tc.session_id = s.session_id
            WHERE 1=1 {date_filter}
            GROUP BY COALESCE(s.cc_version, 'unknown')
        ) tc_stats
        LEFT JOIN (
            SELECT
                COALESCE(s.cc_version, 'unknown') as version,
                SUM(t.cost) as cost
            FROM sessions s
            LEFT JOIN turns t ON t.session_id = s.session_id
            WHERE 1=1 {date_filter}
            GROUP BY COALESCE(s.cc_version, 'unknown')
        ) turn_stats ON turn_stats.version = tc_stats.version
        LEFT JOIN (
            SELECT
                COALESCE(s.cc_version, 'unknown') as version,
                AVG(s.duration_seconds) as avg_duration
            FROM sessions s
            WHERE 1=1 {date_filter}
            GROUP BY COALESCE(s.cc_version, 'unknown')
        ) sess_stats ON sess_stats.version = tc_stats.version
        ORDER BY tc_stats.first_seen
    """, params + params + params)

    eff_rows = cursor.fetchall()

    if eff_rows:
        headers = ['Version', 'LOC Written', 'Cost/KLOC', 'Tool Calls', 'Tool Success Rate', 'Avg Session Duration']
        alignments = ['l', 'r', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in eff_rows:
            version = r['version']
            loc = r['loc_written'] or 0
            cost = r['cost'] or 0
            tool_calls = r['tool_calls'] or 0
            successes = r['successes'] or 0
            avg_duration = r['avg_duration'] or 0

            cost_per_kloc = format_currency(cost / (loc / 1000)) if loc > 0 else '-'
            success_rate = (successes / tool_calls * 100) if tool_calls > 0 else 0

            success_str = format_percentage(success_rate, 1)
            if success_rate < 80:
                success_str = colorize(success_str, Colors.RED, color_enabled)
            elif success_rate < 90:
                success_str = colorize(success_str, Colors.YELLOW, color_enabled)

            table_rows.append([
                version,
                format_number(loc),
                cost_per_kloc,
                format_number(tool_calls),
                success_str,
                format_duration(int(avg_duration)),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
    else:
        lines.append("No efficiency data available.")

    # ── Section 3: Version Error Rates ────────────────────────────
    lines.append("")
    lines.append(bold("VERSION ERROR RATES", color_enabled))
    lines.append("")

    cursor = conn.execute(f"""
        SELECT
            COALESCE(s.cc_version, 'unknown') as version,
            COUNT(tc.rowid) as total_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors,
            MIN(s.first_timestamp) as first_seen
        FROM sessions s
        JOIN tool_calls tc ON tc.session_id = s.session_id
        WHERE 1=1 {date_filter}
        GROUP BY COALESCE(s.cc_version, 'unknown')
        ORDER BY MIN(s.first_timestamp)
    """, params)

    err_rows = cursor.fetchall()

    if err_rows:
        headers = ['Version', 'Total Tool Calls', 'Errors', 'Error Rate']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in err_rows:
            version = r['version']
            total_calls = r['total_calls'] or 0
            errors = r['errors'] or 0
            error_rate = (errors / total_calls * 100) if total_calls > 0 else 0

            rate_str = format_percentage(error_rate, 1)
            if error_rate >= 10:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)
            elif error_rate >= 5:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)
            else:
                rate_str = colorize(rate_str, Colors.GREEN, color_enabled)

            table_rows.append([
                version,
                format_number(total_calls),
                format_number(errors),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
    else:
        lines.append("No tool call data available.")

    # ── Section 4: Version Adoption Timeline (Last 30 Days) ──────
    lines.append("")
    lines.append(bold("VERSION ADOPTION TIMELINE (LAST 30 DAYS)", color_enabled))
    lines.append("")

    cursor = conn.execute(f"""
        SELECT
            date(s.first_timestamp) as date,
            COALESCE(s.cc_version, 'unknown') as version,
            COUNT(DISTINCT s.session_id) as sessions,
            SUM(t.cost) as cost
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE date(s.first_timestamp) >= date('now', '-30 days')
            {date_filter}
        GROUP BY date(s.first_timestamp), COALESCE(s.cc_version, 'unknown')
        ORDER BY date(s.first_timestamp) DESC
    """, params)

    timeline_rows = cursor.fetchall()

    if timeline_rows:
        # Group by date and find primary version per day
        daily_data: Dict[str, list] = {}
        for r in timeline_rows:
            date_str = r['date']
            if date_str not in daily_data:
                daily_data[date_str] = []
            daily_data[date_str].append(r)

        headers = ['Date', 'Primary Version', 'Sessions', 'Cost']
        alignments = ['l', 'l', 'r', 'r']
        table_rows = []

        for date_str in sorted(daily_data.keys(), reverse=True):
            day_rows = daily_data[date_str]
            # Primary version is the one with the most sessions that day
            primary = max(day_rows, key=lambda x: x['sessions'])
            day_sessions = sum(r['sessions'] for r in day_rows)
            day_cost = sum(r['cost'] or 0 for r in day_rows)

            table_rows.append([
                date_str,
                primary['version'],
                format_number(day_sessions),
                format_currency(day_cost),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
    else:
        lines.append("No timeline data available.")

    # ── Section 5: Version Comparison: Latest vs Previous ─────────
    # Determine the two most recent versions by first_seen timestamp
    cursor = conn.execute(f"""
        SELECT
            COALESCE(s.cc_version, 'unknown') as version,
            MIN(s.first_timestamp) as first_seen
        FROM sessions s
        WHERE COALESCE(s.cc_version, 'unknown') != 'unknown'
            {date_filter}
        GROUP BY COALESCE(s.cc_version, 'unknown')
        ORDER BY MIN(s.first_timestamp) DESC
        LIMIT 2
    """, params)

    version_order = cursor.fetchall()

    if len(version_order) >= 2:
        latest_version = version_order[0]['version']
        previous_version = version_order[1]['version']

        lines.append("")
        lines.append(bold(f"VERSION COMPARISON: {latest_version} vs {previous_version}", color_enabled))
        lines.append("")

        # Gather stats for both versions
        comparison = {}
        for version in [latest_version, previous_version]:
            v_params = [version] + params
            cursor = conn.execute(f"""
                SELECT
                    COUNT(DISTINCT s.session_id) as sessions,
                    SUM(t.cost) as cost,
                    AVG(s.duration_seconds) as avg_duration
                FROM sessions s
                LEFT JOIN turns t ON t.session_id = s.session_id
                WHERE s.cc_version = ?
                    {date_filter}
            """, v_params)
            v_stats = cursor.fetchone()

            cursor = conn.execute(f"""
                SELECT
                    COUNT(tc.rowid) as tool_calls,
                    SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors,
                    SUM(tc.loc_written) as loc_written
                FROM sessions s
                JOIN tool_calls tc ON tc.session_id = s.session_id
                WHERE s.cc_version = ?
                    {date_filter}
            """, v_params)
            t_stats = cursor.fetchone()

            sessions = v_stats['sessions'] or 0
            cost = v_stats['cost'] or 0
            tool_calls = t_stats['tool_calls'] or 0
            errors = t_stats['errors'] or 0
            loc = t_stats['loc_written'] or 0

            comparison[version] = {
                'sessions': sessions,
                'avg_cost': (cost / sessions) if sessions > 0 else 0,
                'error_rate': (errors / tool_calls * 100) if tool_calls > 0 else 0,
                'avg_duration': v_stats['avg_duration'] or 0,
                'loc_per_session': (loc / sessions) if sessions > 0 else 0,
            }

        latest = comparison[latest_version]
        previous = comparison[previous_version]

        headers = ['Metric', latest_version, previous_version, 'Change']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        # Sessions
        table_rows.append([
            'Sessions',
            format_number(latest['sessions']),
            format_number(previous['sessions']),
            _format_change(latest['sessions'], previous['sessions'],
                           is_lower_better=False, color_enabled=color_enabled),
        ])

        # Avg Cost/Session (lower is better)
        table_rows.append([
            'Avg Cost/Session',
            format_currency(latest['avg_cost']),
            format_currency(previous['avg_cost']),
            _format_change(latest['avg_cost'], previous['avg_cost'],
                           is_lower_better=True, color_enabled=color_enabled),
        ])

        # Error Rate (lower is better)
        table_rows.append([
            'Error Rate',
            format_percentage(latest['error_rate'], 1),
            format_percentage(previous['error_rate'], 1),
            _format_change(latest['error_rate'], previous['error_rate'],
                           is_lower_better=True, color_enabled=color_enabled),
        ])

        # Avg Duration
        table_rows.append([
            'Avg Duration',
            format_duration(int(latest['avg_duration'])),
            format_duration(int(previous['avg_duration'])),
            _format_change(latest['avg_duration'], previous['avg_duration'],
                           is_lower_better=True, color_enabled=color_enabled),
        ])

        # LOC/Session (higher is better)
        table_rows.append([
            'LOC/Session',
            format_number(latest['loc_per_session'], 1),
            format_number(previous['loc_per_session'], 1),
            _format_change(latest['loc_per_session'], previous['loc_per_session'],
                           is_lower_better=False, color_enabled=color_enabled),
        ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))

    return '\n'.join(lines)


def _format_change(
    current: float,
    previous: float,
    is_lower_better: bool,
    color_enabled: bool
) -> str:
    """Format a percentage change with color indicating improvement or regression."""
    if previous == 0:
        if current == 0:
            return "N/A"
        return colorize("+inf", Colors.RED if not is_lower_better else Colors.GREEN, color_enabled)

    pct = ((current - previous) / previous) * 100
    sign = '+' if pct >= 0 else ''
    result = f"{sign}{pct:.1f}%"

    if abs(pct) < 0.1:
        return result

    if is_lower_better:
        color = Colors.GREEN if pct < 0 else Colors.RED
    else:
        color = Colors.GREEN if pct > 0 else Colors.RED

    return colorize(result, color, color_enabled)
