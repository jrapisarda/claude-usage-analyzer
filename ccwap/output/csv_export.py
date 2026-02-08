"""
CSV export functionality for CCWAP.

Handles --export flag to export reports to CSV files.
"""

import csv
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional, List


def export_daily(
    conn: sqlite3.Connection,
    output_path: Path,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> int:
    """Export daily data to CSV."""
    if date_to is None:
        date_to = datetime.now()
    if date_from is None:
        from datetime import timedelta
        date_from = date_to - timedelta(days=30)

    cursor = conn.execute("""
        SELECT
            date(timestamp) as date,
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as turns,
            SUM(CASE WHEN entry_type = 'user' THEN 1 ELSE 0 END) as user_turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read,
            SUM(cache_write_tokens) as cache_write,
            SUM(cost) as cost
        FROM turns
        WHERE date(timestamp) >= date(?)
        AND date(timestamp) <= date(?)
        GROUP BY date(timestamp)
        ORDER BY date DESC
    """, (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

    rows = cursor.fetchall()
    return _write_csv(output_path, rows, [
        'date', 'sessions', 'turns', 'user_turns',
        'input_tokens', 'output_tokens', 'cache_read', 'cache_write', 'cost'
    ])


def export_projects(
    conn: sqlite3.Connection,
    output_path: Path,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    project_filter: Optional[str] = None
) -> int:
    """Export project data to CSV."""
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

    cursor = conn.execute(f"""
        SELECT
            s.project_path,
            s.project_display,
            COUNT(DISTINCT s.session_id) as sessions,
            SUM(CASE WHEN s.is_agent = 0 AND t.entry_type IN ('user', 'assistant') THEN 1 ELSE 0 END) as messages,
            SUM(CASE WHEN s.is_agent = 0 AND t.entry_type = 'user' THEN 1 ELSE 0 END) as user_turns,
            SUM(t.input_tokens) as input_tokens,
            SUM(t.output_tokens) as output_tokens,
            SUM(t.cache_read_tokens) as cache_read_tokens,
            SUM(t.cache_write_tokens) as cache_write_tokens,
            SUM(t.cost) as cost
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE 1=1 {date_filter} {project_filter_sql}
        GROUP BY s.project_path, s.project_display
        ORDER BY cost DESC
    """, params)

    rows = cursor.fetchall()
    return _write_csv(output_path, rows, [
        'project_path', 'project_display', 'sessions', 'messages', 'user_turns',
        'input_tokens', 'output_tokens', 'cache_read_tokens', 'cache_write_tokens', 'cost'
    ])


def export_tools(
    conn: sqlite3.Connection,
    output_path: Path,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> int:
    """Export tool usage data to CSV."""
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

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
    return _write_csv(output_path, rows, [
        'tool_name', 'calls', 'successes', 'failures',
        'loc_written', 'lines_added', 'lines_deleted'
    ])


def export_errors(
    conn: sqlite3.Connection,
    output_path: Path,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> int:
    """Export error data to CSV."""
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
            tc.timestamp,
            s.project_display,
            tc.tool_name,
            tc.error_category,
            tc.error_message,
            tc.file_path
        FROM tool_calls tc
        JOIN sessions s ON s.session_id = tc.session_id
        WHERE tc.success = 0 {date_filter}
        ORDER BY tc.timestamp DESC
    """, params)

    rows = cursor.fetchall()
    return _write_csv(output_path, rows, [
        'timestamp', 'project_display', 'tool_name', 'error_category', 'error_message', 'file_path'
    ])


def export_sessions(
    conn: sqlite3.Connection,
    output_path: Path,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> int:
    """Export session data to CSV."""
    filters = []
    params = []

    if date_from:
        filters.append("date(first_timestamp) >= date(?)")
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        filters.append("date(first_timestamp) <= date(?)")
        params.append(date_to.strftime('%Y-%m-%d'))

    where_clause = " AND ".join(filters) if filters else "1=1"

    cursor = conn.execute(f"""
        SELECT
            s.session_id,
            s.project_display,
            s.first_timestamp,
            s.last_timestamp,
            s.duration_seconds,
            s.is_agent,
            s.cc_version,
            COUNT(t.id) as turns,
            SUM(t.input_tokens) as input_tokens,
            SUM(t.output_tokens) as output_tokens,
            SUM(t.cost) as cost
        FROM sessions s
        LEFT JOIN turns t ON t.session_id = s.session_id
        WHERE {where_clause}
        GROUP BY s.session_id
        ORDER BY s.first_timestamp DESC
    """, params)

    rows = cursor.fetchall()
    return _write_csv(output_path, rows, [
        'session_id', 'project_display', 'first_timestamp', 'last_timestamp',
        'duration_seconds', 'is_agent', 'cc_version',
        'turns', 'input_tokens', 'output_tokens', 'cost'
    ])


def export_summary(
    conn: sqlite3.Connection,
    output_path: Path
) -> int:
    """Export summary data to CSV."""
    # Overall stats
    cursor = conn.execute("""
        SELECT
            'All Time' as period,
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read,
            SUM(cache_write_tokens) as cache_write,
            SUM(cost) as cost
        FROM turns
    """)

    rows = [cursor.fetchone()]

    # Today's stats
    cursor = conn.execute("""
        SELECT
            'Today' as period,
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read,
            SUM(cache_write_tokens) as cache_write,
            SUM(cost) as cost
        FROM turns
        WHERE date(timestamp) = date('now')
    """)

    rows.append(cursor.fetchone())

    return _write_csv(output_path, rows, [
        'period', 'sessions', 'turns', 'input_tokens', 'output_tokens',
        'cache_read', 'cache_write', 'cost'
    ])


def _write_csv(output_path: Path, rows: List, headers: List[str]) -> int:
    """Write rows to CSV file."""
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.writer(f)
        writer.writerow(headers)

        for row in rows:
            writer.writerow([row[h] if row[h] is not None else '' for h in headers])

    return len(rows)


def export_report(
    conn: sqlite3.Connection,
    output_path: str,
    report_type: str,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    project_filter: Optional[str] = None
) -> str:
    """
    Export a report to CSV.

    Args:
        conn: Database connection
        output_path: Path to output file
        report_type: Type of report (daily, projects, tools, errors, sessions, summary)
        date_from: Start date filter
        date_to: End date filter
        project_filter: Project name filter

    Returns:
        Status message
    """
    path = Path(output_path)

    exporters = {
        'daily': lambda: export_daily(conn, path, date_from, date_to),
        'projects': lambda: export_projects(conn, path, date_from, date_to, project_filter),
        'tools': lambda: export_tools(conn, path, date_from, date_to),
        'errors': lambda: export_errors(conn, path, date_from, date_to),
        'sessions': lambda: export_sessions(conn, path, date_from, date_to),
        'summary': lambda: export_summary(conn, path),
    }

    if report_type not in exporters:
        # Default to summary
        report_type = 'summary'

    count = exporters[report_type]()
    return f"Exported {count} rows to {output_path}"
