"""
Projects report for CCWAP.

Generates the --projects view with all 30+ metrics per project.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens, format_percentage,
    format_table, format_duration, bold, colorize, Colors
)
from ccwap.models.entities import ProjectStats


def generate_projects(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    project_filter: Optional[str] = None,
    sort_by: str = 'cost',
    color_enabled: bool = True
) -> str:
    """
    Generate comprehensive project report.

    Shows all 30+ metrics per project.
    FIXES BUG 5: Uses accurate per-model cost from stored turn costs.
    FIXES BUG 8: Includes agent file costs in totals.
    """
    lines = []
    lines.append(bold("PROJECT METRICS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build query with optional filters
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(t.timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(t.timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    project_filter_sql = ""
    if project_filter:
        project_filter_sql = " AND s.project_display LIKE ?"
        params.append(f"%{project_filter}%")

    # Query project data
    # Note: Agent files have is_agent=1, their costs are included but messages excluded
    cursor = conn.execute(f"""
        SELECT
            s.project_path,
            s.project_display,
            COUNT(DISTINCT s.session_id) as sessions,
            COUNT(DISTINCT CASE WHEN s.is_agent = 1 THEN s.session_id END) as agent_sessions,
            SUM(CASE WHEN s.is_agent = 0 AND t.entry_type IN ('user', 'assistant') THEN 1 ELSE 0 END) as messages,
            SUM(CASE WHEN s.is_agent = 0 AND t.entry_type = 'user' THEN 1 ELSE 0 END) as user_turns,
            SUM(t.input_tokens) as input_tokens,
            SUM(t.output_tokens) as output_tokens,
            SUM(t.cache_read_tokens) as cache_read_tokens,
            SUM(t.cache_write_tokens) as cache_write_tokens,
            SUM(t.thinking_chars) as thinking_chars,
            SUM(t.cost) as cost,
            SUM(CASE WHEN t.is_meta = 1 THEN 1 ELSE 0 END) as skill_invocations,
            SUM(s.duration_seconds) as duration_seconds,
            MAX(s.cc_version) as cc_version,
            MAX(s.git_branch) as git_branch
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE 1=1 {date_filter} {project_filter_sql}
        GROUP BY s.project_path, s.project_display
        ORDER BY cost DESC
    """, params)

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo project data found."

    # Get tool call stats per project
    tool_stats = _get_tool_stats_by_project(conn, date_from, date_to)

    # Build project stats
    projects = []
    for r in rows:
        project_path = r['project_path']
        ts = tool_stats.get(project_path, {})

        stats = ProjectStats(
            project_path=project_path,
            project_display=r['project_display'] or project_path,
            sessions=r['sessions'] or 0,
            messages=r['messages'] or 0,
            user_turns=r['user_turns'] or 0,
            input_tokens=r['input_tokens'] or 0,
            output_tokens=r['output_tokens'] or 0,
            cache_read_tokens=r['cache_read_tokens'] or 0,
            cache_write_tokens=r['cache_write_tokens'] or 0,
            thinking_chars=r['thinking_chars'] or 0,
            cost=r['cost'] or 0,
            skill_invocations=r['skill_invocations'] or 0,
            duration_seconds=r['duration_seconds'] or 0,
            cc_version=r['cc_version'],
            git_branch=r['git_branch'],
            agent_spawns=r['agent_sessions'] or 0,
            loc_written=ts.get('loc_written', 0),
            lines_added=ts.get('lines_added', 0),
            lines_deleted=ts.get('lines_deleted', 0),
            files_created=ts.get('files_created', 0),
            files_edited=ts.get('files_edited', 0),
            tool_calls=ts.get('tool_calls', 0),
            error_count=ts.get('errors', 0),
        )
        stats.calculate_derived_metrics()
        projects.append(stats)

    # Format table
    headers = ['Project', 'Sessions', 'Turns', 'LOC', 'Tokens', 'Cost', 'Err%']
    alignments = ['l', 'r', 'r', 'r', 'r', 'r', 'r']
    table_rows = []

    for p in projects:
        name = p.project_display
        if len(name) > 35:
            name = name[:32] + '...'

        total_tokens = p.input_tokens + p.output_tokens
        error_pct = p.error_rate * 100 if p.tool_calls > 0 else 0

        # Color high error rates
        err_str = format_percentage(error_pct, 1)
        if error_pct > 10:
            err_str = colorize(err_str, Colors.RED, color_enabled)

        table_rows.append([
            name,
            format_number(p.sessions),
            format_number(p.user_turns),
            format_number(p.loc_written),
            format_tokens(total_tokens),
            format_currency(p.cost),
            err_str,
        ])

    # Totals
    total_stats = _aggregate_project_stats(projects)
    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_number(total_stats['sessions']), color_enabled),
        bold(format_number(total_stats['user_turns']), color_enabled),
        bold(format_number(total_stats['loc_written']), color_enabled),
        bold(format_tokens(total_stats['tokens']), color_enabled),
        bold(format_currency(total_stats['cost']), color_enabled),
        '',
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # Efficiency metrics
    lines.append("")
    lines.append(bold("EFFICIENCY METRICS", color_enabled))
    lines.append("-" * 40)

    if total_stats['loc_written'] > 0:
        cost_per_kloc = total_stats['cost'] / (total_stats['loc_written'] / 1000)
        tokens_per_loc = total_stats['output_tokens'] / total_stats['loc_written']
        lines.append(f"Cost per KLOC:      {format_currency(cost_per_kloc)}")
        lines.append(f"Tokens per LOC:     {format_number(tokens_per_loc, 1)}")

    if total_stats['input_tokens'] + total_stats['cache_read'] > 0:
        cache_rate = total_stats['cache_read'] / (total_stats['input_tokens'] + total_stats['cache_read']) * 100
        lines.append(f"Cache Hit Rate:     {format_percentage(cache_rate)}")

    return '\n'.join(lines)


def _get_tool_stats_by_project(
    conn: sqlite3.Connection,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> Dict[str, Dict[str, int]]:
    """Get tool call statistics grouped by project."""
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(tc.timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(tc.timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    cursor = conn.execute(f"""
        SELECT
            s.project_path,
            COUNT(*) as tool_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors,
            SUM(tc.loc_written) as loc_written,
            SUM(tc.lines_added) as lines_added,
            SUM(tc.lines_deleted) as lines_deleted,
            COUNT(DISTINCT CASE WHEN tc.tool_name = 'Write' THEN tc.file_path END) as files_created,
            COUNT(DISTINCT CASE WHEN tc.tool_name = 'Edit' THEN tc.file_path END) as files_edited
        FROM tool_calls tc
        JOIN sessions s ON s.session_id = tc.session_id
        WHERE 1=1 {date_filter}
        GROUP BY s.project_path
    """, params)

    result = {}
    for row in cursor.fetchall():
        result[row['project_path']] = {
            'tool_calls': row['tool_calls'] or 0,
            'errors': row['errors'] or 0,
            'loc_written': row['loc_written'] or 0,
            'lines_added': row['lines_added'] or 0,
            'lines_deleted': row['lines_deleted'] or 0,
            'files_created': row['files_created'] or 0,
            'files_edited': row['files_edited'] or 0,
        }

    return result


def _aggregate_project_stats(projects: List[ProjectStats]) -> Dict[str, Any]:
    """Aggregate statistics across all projects."""
    return {
        'sessions': sum(p.sessions for p in projects),
        'user_turns': sum(p.user_turns for p in projects),
        'loc_written': sum(p.loc_written for p in projects),
        'tokens': sum(p.input_tokens + p.output_tokens for p in projects),
        'output_tokens': sum(p.output_tokens for p in projects),
        'cost': sum(p.cost for p in projects),
        'input_tokens': sum(p.input_tokens for p in projects),
        'cache_read': sum(p.cache_read_tokens for p in projects),
    }
