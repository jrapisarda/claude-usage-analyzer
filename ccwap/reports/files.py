"""
File hotspot analysis report for CCWAP.

Generates the --files view with per-file change tracking.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage,
    format_table, bold, colorize, Colors, create_bar
)


def truncate_path(path, max_len=40):
    """Truncate a file path from the left, showing the end."""
    if not path:
        return 'Unknown'
    if len(path) <= max_len:
        return path
    return '...' + path[-(max_len - 3):]


def generate_files(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate file hotspot analysis report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("FILE HOTSPOT ANALYSIS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build query with optional date filters
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(tc.timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(tc.timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # ── SUMMARY ──────────────────────────────────────────────────
    cursor = conn.execute(f"""
        SELECT
            COUNT(DISTINCT tc.file_path) as unique_files,
            COUNT(*) as total_ops,
            SUM(tc.lines_added) as total_added,
            SUM(tc.lines_deleted) as total_deleted
        FROM tool_calls tc
        WHERE tc.file_path IS NOT NULL
        {date_filter}
    """, params)

    summary = cursor.fetchone()
    unique_files = summary['unique_files'] or 0
    total_ops = summary['total_ops'] or 0
    total_added = summary['total_added'] or 0
    total_deleted = summary['total_deleted'] or 0
    total_churn = total_added + total_deleted

    if total_ops == 0:
        return lines[0] + "\n\nNo file operation data found."

    lines.append(bold("SUMMARY", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Unique files touched:  {format_number(unique_files)}")
    lines.append(f"Total file operations: {format_number(total_ops)}")
    lines.append(f"Total lines added:     {colorize(f'+{format_number(total_added)}', Colors.GREEN, color_enabled)}")
    lines.append(f"Total lines deleted:   {colorize(f'-{format_number(total_deleted)}', Colors.RED, color_enabled)}")
    lines.append(f"Total churn:           {format_number(total_churn)}")
    lines.append("")

    # ── MOST MODIFIED FILES (Top 20) ─────────────────────────────
    cursor = conn.execute(f"""
        SELECT
            tc.file_path,
            COUNT(*) as operations,
            SUM(tc.lines_added) as lines_added,
            SUM(tc.lines_deleted) as lines_deleted,
            SUM(tc.lines_added) + SUM(tc.lines_deleted) as churn,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls tc
        WHERE tc.file_path IS NOT NULL
        {date_filter}
        GROUP BY tc.file_path
        ORDER BY churn DESC
        LIMIT 20
    """, params)

    mod_rows = cursor.fetchall()

    if mod_rows:
        lines.append(bold("MOST MODIFIED FILES", color_enabled))

        max_churn = max(r['churn'] for r in mod_rows) if mod_rows else 1

        headers = ['File Path', 'Ops', '+Lines', '-Lines', 'Churn', 'Errors', 'Bar']
        alignments = ['l', 'r', 'r', 'r', 'r', 'r', 'l']
        table_rows = []

        for r in mod_rows:
            file_path = truncate_path(r['file_path'])
            operations = r['operations']
            added = r['lines_added'] or 0
            deleted = r['lines_deleted'] or 0
            churn = r['churn'] or 0
            errors = r['errors'] or 0

            error_str = format_number(errors)
            if errors > 0:
                error_str = colorize(error_str, Colors.RED, color_enabled)

            bar = create_bar(churn, max_churn, width=15)

            table_rows.append([
                file_path,
                format_number(operations),
                format_number(added),
                format_number(deleted),
                format_number(churn),
                error_str,
                bar,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── HIGHEST ERROR FILES (Top 10) ─────────────────────────────
    cursor = conn.execute(f"""
        SELECT
            tc.file_path,
            COUNT(*) as total_ops,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls tc
        WHERE tc.file_path IS NOT NULL
        {date_filter}
        GROUP BY tc.file_path
        HAVING errors > 0
        ORDER BY errors DESC
        LIMIT 10
    """, params)

    error_rows = cursor.fetchall()

    if error_rows:
        lines.append(bold("HIGHEST ERROR FILES", color_enabled))

        headers = ['File Path', 'Total Ops', 'Errors', 'Error Rate']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in error_rows:
            file_path = truncate_path(r['file_path'])
            total = r['total_ops']
            errors = r['errors']
            rate = (errors / total * 100) if total > 0 else 0

            rate_str = format_percentage(rate, 1)
            if rate > 10:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)
            elif rate > 5:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)

            table_rows.append([
                file_path,
                format_number(total),
                format_number(errors),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── FILE ACTIVITY BY LANGUAGE ────────────────────────────────
    cursor = conn.execute(f"""
        SELECT
            tc.language,
            COUNT(DISTINCT tc.file_path) as files,
            COUNT(*) as operations,
            SUM(tc.loc_written) as loc_written,
            SUM(tc.lines_added) as lines_added,
            SUM(tc.lines_deleted) as lines_deleted
        FROM tool_calls tc
        WHERE tc.file_path IS NOT NULL
        AND tc.language IS NOT NULL
        AND tc.language != ''
        {date_filter}
        GROUP BY tc.language
        ORDER BY loc_written DESC
    """, params)

    lang_rows = cursor.fetchall()

    if lang_rows:
        lines.append(bold("FILE ACTIVITY BY LANGUAGE", color_enabled))

        headers = ['Language', 'Files', 'Operations', 'LOC Written', '+Lines', '-Lines']
        alignments = ['l', 'r', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in lang_rows:
            language = r['language']
            files = r['files'] or 0
            operations = r['operations']
            loc = r['loc_written'] or 0
            added = r['lines_added'] or 0
            deleted = r['lines_deleted'] or 0

            table_rows.append([
                language,
                format_number(files),
                format_number(operations),
                format_number(loc),
                format_number(added),
                format_number(deleted),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── MOST TOUCHED FILES BY SESSION COUNT ──────────────────────
    cursor = conn.execute(f"""
        SELECT
            tc.file_path,
            COUNT(DISTINCT tc.session_id) as sessions,
            COUNT(*) as operations
        FROM tool_calls tc
        WHERE tc.file_path IS NOT NULL
        {date_filter}
        GROUP BY tc.file_path
        ORDER BY sessions DESC
        LIMIT 15
    """, params)

    session_rows = cursor.fetchall()

    if session_rows:
        lines.append(bold("MOST TOUCHED FILES BY SESSION COUNT", color_enabled))

        headers = ['File Path', 'Sessions', 'Operations']
        alignments = ['l', 'r', 'r']
        table_rows = []

        for r in session_rows:
            file_path = truncate_path(r['file_path'])
            sessions = r['sessions']
            operations = r['operations']

            table_rows.append([
                file_path,
                format_number(sessions),
                format_number(operations),
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── RECENT FILE ACTIVITY ─────────────────────────────────────
    cursor = conn.execute(f"""
        SELECT
            tc.timestamp,
            tc.tool_name,
            tc.file_path,
            tc.lines_added,
            tc.lines_deleted,
            tc.success
        FROM tool_calls tc
        WHERE tc.file_path IS NOT NULL
        {date_filter}
        ORDER BY tc.timestamp DESC
        LIMIT 10
    """, params)

    recent_rows = cursor.fetchall()

    if recent_rows:
        lines.append(bold("RECENT FILE ACTIVITY", color_enabled))

        headers = ['Timestamp', 'Tool', 'File Path', 'Lines +/-', 'Status']
        alignments = ['l', 'l', 'l', 'r', 'l']
        table_rows = []

        for r in recent_rows:
            timestamp = r['timestamp']
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime('%m-%d %H:%M')
                except Exception:
                    time_str = timestamp[:10]
            else:
                time_str = 'Unknown'

            tool = r['tool_name'] or 'Unknown'
            file_path = truncate_path(r['file_path'])
            added = r['lines_added'] or 0
            deleted = r['lines_deleted'] or 0
            lines_str = f"+{added}/-{deleted}"

            if r['success']:
                status = colorize("Success", Colors.GREEN, color_enabled)
            else:
                status = colorize("Fail", Colors.RED, color_enabled)

            table_rows.append([
                time_str,
                tool,
                file_path,
                lines_str,
                status,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))

    return '\n'.join(lines)
