"""
Skill invocation analytics report for CCWAP.

Generates the --skills view analyzing skill and agent usage patterns.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, bold, colorize, Colors, create_bar
)


def generate_skills(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate skill invocation analytics report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("SKILL INVOCATION ANALYTICS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build date filter for turns
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(t.timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(t.timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # ── Section 1: Skill Usage Overview ──────────────────────────
    cursor = conn.execute(f"""
        SELECT
            COUNT(*) as total_turns,
            SUM(CASE WHEN t.is_meta = 1 THEN 1 ELSE 0 END) as skill_turns,
            SUM(CASE WHEN t.is_meta = 1 THEN t.cost ELSE 0 END) as skill_cost,
            SUM(t.cost) as total_cost
        FROM turns t
        WHERE 1=1 {date_filter}
    """, params)

    summary = cursor.fetchone()
    total_turns = summary['total_turns'] or 0
    skill_turns = summary['skill_turns'] or 0
    skill_cost = summary['skill_cost'] or 0
    total_cost = summary['total_cost'] or 0

    if total_turns == 0:
        return lines[0] + "\n\nNo data found."

    skill_pct = (skill_turns / total_turns * 100) if total_turns > 0 else 0

    # Get agent spawns from daily_summaries
    ds_date_filter = ""
    ds_params = []
    if date_from:
        ds_date_filter += " AND date(date) >= date(?)"
        ds_params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        ds_date_filter += " AND date(date) <= date(?)"
        ds_params.append(date_to.strftime('%Y-%m-%d'))

    cursor = conn.execute(f"""
        SELECT
            COALESCE(SUM(agent_spawns), 0) as total_agent_spawns
        FROM daily_summaries
        WHERE 1=1 {ds_date_filter}
    """, ds_params)

    agent_row = cursor.fetchone()
    total_agent_spawns = agent_row['total_agent_spawns'] or 0

    lines.append(bold("SKILL USAGE OVERVIEW", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Total skill invocations: {format_number(skill_turns)}")
    lines.append(f"Total skill cost:        {format_currency(skill_cost)}")
    lines.append(f"Skill turns % of all:    {format_percentage(skill_pct)}")
    lines.append(f"Total agent spawns:      {format_number(total_agent_spawns)}")
    lines.append("")

    # ── Section 2: Skill Frequency ───────────────────────────────
    lines.append(bold("SKILL FREQUENCY", color_enabled))
    lines.append("")

    cursor = conn.execute(f"""
        SELECT
            COALESCE(tc.command_name, 'unknown') as skill_name,
            COUNT(*) as invocations
        FROM tool_calls tc
        JOIN turns t ON t.id = tc.turn_id
        WHERE t.is_meta = 1 {date_filter}
        GROUP BY skill_name
        ORDER BY invocations DESC
    """, params)

    freq_rows = cursor.fetchall()

    if freq_rows:
        total_skill_calls = sum(r['invocations'] for r in freq_rows)
        max_invocations = max(r['invocations'] for r in freq_rows)

        headers = ['Skill Name', 'Invocations', '% of Total', 'Bar']
        alignments = ['l', 'r', 'r', 'l']
        table_rows = []

        for r in freq_rows:
            skill_name = r['skill_name']
            invocations = r['invocations']
            pct = (invocations / total_skill_calls * 100) if total_skill_calls > 0 else 0
            bar = create_bar(invocations, max_invocations, width=15)

            table_rows.append([
                skill_name,
                format_number(invocations),
                format_percentage(pct, 1),
                bar,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
    else:
        lines.append("No skill command_name data found.")

        # Fallback: show tool_name usage during meta turns
        cursor = conn.execute(f"""
            SELECT
                tc.tool_name,
                COUNT(*) as calls
            FROM tool_calls tc
            JOIN turns t ON t.id = tc.turn_id
            WHERE t.is_meta = 1 {date_filter}
            GROUP BY tc.tool_name
            ORDER BY calls DESC
        """, params)

        tool_rows = cursor.fetchall()

        if tool_rows:
            lines.append("")
            lines.append(bold("TOOL USAGE DURING SKILL TURNS", color_enabled))
            lines.append("")

            total_tool_calls = sum(r['calls'] for r in tool_rows)
            max_calls = max(r['calls'] for r in tool_rows)

            headers = ['Tool Name', 'Calls', '% of Total', 'Bar']
            alignments = ['l', 'r', 'r', 'l']
            table_rows = []

            for r in tool_rows:
                tool_name = r['tool_name']
                calls = r['calls']
                pct = (calls / total_tool_calls * 100) if total_tool_calls > 0 else 0
                bar = create_bar(calls, max_calls, width=15)

                table_rows.append([
                    tool_name,
                    format_number(calls),
                    format_percentage(pct, 1),
                    bar,
                ])

            lines.append(format_table(headers, table_rows, alignments, color_enabled))

    lines.append("")

    # ── Section 3: Skill Cost Analysis ───────────────────────────
    lines.append(bold("SKILL COST ANALYSIS", color_enabled))
    lines.append("")

    non_meta_turns = total_turns - skill_turns
    non_meta_cost = total_cost - skill_cost
    avg_skill_cost = (skill_cost / skill_turns) if skill_turns > 0 else 0
    avg_regular_cost = (non_meta_cost / non_meta_turns) if non_meta_turns > 0 else 0

    headers = ['Category', 'Turns', 'Total Cost', 'Avg Cost/Turn']
    alignments = ['l', 'r', 'r', 'r']
    table_rows = []

    table_rows.append([
        'Skill (meta) turns',
        format_number(skill_turns),
        format_currency(skill_cost),
        format_currency(avg_skill_cost),
    ])

    table_rows.append([
        'Regular turns',
        format_number(non_meta_turns),
        format_currency(non_meta_cost),
        format_currency(avg_regular_cost),
    ])

    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_number(total_turns), color_enabled),
        bold(format_currency(total_cost), color_enabled),
        bold(format_currency(total_cost / total_turns if total_turns > 0 else 0), color_enabled),
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))
    lines.append("")

    # ── Section 4: Skills by Project (Top 10) ────────────────────
    lines.append(bold("SKILLS BY PROJECT (TOP 10)", color_enabled))
    lines.append("")

    cursor = conn.execute(f"""
        SELECT
            s.project_display,
            SUM(CASE WHEN t.is_meta = 1 THEN 1 ELSE 0 END) as skill_invocations,
            SUM(CASE WHEN t.is_meta = 1 THEN t.cost ELSE 0 END) as skill_cost,
            SUM(t.cost) as project_cost
        FROM turns t
        JOIN sessions s ON s.session_id = t.session_id
        WHERE 1=1 {date_filter}
        GROUP BY s.project_display
        HAVING skill_invocations > 0
        ORDER BY skill_cost DESC
        LIMIT 10
    """, params)

    project_rows = cursor.fetchall()

    if project_rows:
        headers = ['Project', 'Skill Invocations', 'Skill Cost', '% of Project Cost']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in project_rows:
            project = r['project_display'] or 'Unknown'
            if len(project) > 35:
                project = project[:32] + '...'

            proj_skill_cost = r['skill_cost'] or 0
            proj_total_cost = r['project_cost'] or 0
            pct_of_project = (proj_skill_cost / proj_total_cost * 100) if proj_total_cost > 0 else 0

            table_rows.append([
                project,
                format_number(r['skill_invocations']),
                format_currency(proj_skill_cost),
                format_percentage(pct_of_project, 1),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
    else:
        lines.append("No skill usage by project found.")

    lines.append("")

    # ── Section 5: Skill Usage Trend (Last 14 Days) ──────────────
    lines.append(bold("SKILL USAGE TREND (LAST 14 DAYS)", color_enabled))
    lines.append("")

    cursor = conn.execute(f"""
        SELECT
            date(t.timestamp) as date,
            SUM(CASE WHEN t.is_meta = 1 THEN 1 ELSE 0 END) as skill_invocations,
            SUM(CASE WHEN t.is_meta = 0 THEN 1 ELSE 0 END) as regular_turns,
            COUNT(*) as total_day_turns,
            SUM(CASE WHEN t.is_meta = 1 THEN t.cost ELSE 0 END) as skill_cost
        FROM turns t
        WHERE date(t.timestamp) >= date('now', '-14 days')
            {date_filter}
        GROUP BY date(t.timestamp)
        ORDER BY date(t.timestamp) DESC
    """, params)

    trend_rows = cursor.fetchall()

    if trend_rows:
        headers = ['Date', 'Skill Invocations', 'Regular Turns', 'Skill %', 'Skill Cost']
        alignments = ['l', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in trend_rows:
            skill_inv = r['skill_invocations'] or 0
            regular = r['regular_turns'] or 0
            total_day = r['total_day_turns'] or 0
            s_cost = r['skill_cost'] or 0
            s_pct = (skill_inv / total_day * 100) if total_day > 0 else 0

            table_rows.append([
                r['date'],
                format_number(skill_inv),
                format_number(regular),
                format_percentage(s_pct, 1),
                format_currency(s_cost),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
    else:
        lines.append("No trend data available.")

    lines.append("")

    # ── Section 6: Agent Spawn Analysis ──────────────────────────
    lines.append(bold("AGENT SPAWN ANALYSIS", color_enabled))
    lines.append("-" * 40)

    # Agent spawns from daily_summaries
    cursor = conn.execute(f"""
        SELECT
            COALESCE(SUM(agent_spawns), 0) as total_spawns,
            COALESCE(AVG(CASE WHEN agent_spawns > 0 THEN agent_spawns END), 0) as daily_avg,
            MAX(agent_spawns) as peak_spawns,
            (SELECT date FROM daily_summaries
             WHERE agent_spawns = (
                 SELECT MAX(agent_spawns) FROM daily_summaries WHERE 1=1 {ds_date_filter}
             ) {ds_date_filter}
             LIMIT 1) as peak_date
        FROM daily_summaries
        WHERE 1=1 {ds_date_filter}
    """, ds_params + ds_params)

    spawn_row = cursor.fetchone()
    total_spawns = spawn_row['total_spawns'] or 0
    daily_avg = spawn_row['daily_avg'] or 0
    peak_spawns = spawn_row['peak_spawns'] or 0
    peak_date = spawn_row['peak_date'] or 'N/A'

    lines.append(f"Total agent spawns:      {format_number(total_spawns)}")
    lines.append(f"Daily average:           {format_number(daily_avg, 1)}")
    lines.append(f"Peak day:                {peak_date} ({format_number(peak_spawns)} spawns)")
    lines.append("")

    # Agent sessions from sessions table
    cursor = conn.execute(f"""
        SELECT
            COUNT(*) as agent_sessions,
            COALESCE(SUM(t.cost), 0) as agent_cost
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE s.is_agent = 1 {date_filter}
    """, params)

    agent_session_row = cursor.fetchone()
    agent_sessions = agent_session_row['agent_sessions'] or 0
    agent_cost = agent_session_row['agent_cost'] or 0

    lines.append(f"Total agent sessions:    {format_number(agent_sessions)}")
    lines.append(f"Total agent session cost: {format_currency(agent_cost)}")

    return '\n'.join(lines)
