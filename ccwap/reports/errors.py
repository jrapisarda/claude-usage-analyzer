"""
Errors report for CCWAP.

Generates the --errors view with error categorization and analysis.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage,
    format_table, bold, colorize, Colors, create_bar
)


def generate_errors(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate error analysis report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("ERROR ANALYSIS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build query with optional date filters
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # Query error summary
    cursor = conn.execute(f"""
        SELECT
            COUNT(*) as total_calls,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls
        WHERE 1=1 {date_filter}
    """, params)

    summary = cursor.fetchone()
    total_calls = summary['total_calls'] or 0
    total_errors = summary['errors'] or 0

    if total_calls == 0:
        return lines[0] + "\n\nNo tool call data found."

    error_rate = (total_errors / total_calls * 100) if total_calls > 0 else 0

    # Summary stats
    lines.append(bold("SUMMARY", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Total tool calls:     {format_number(total_calls)}")

    error_str = format_number(total_errors)
    if total_errors > 0:
        error_str = colorize(error_str, Colors.RED, color_enabled)
    lines.append(f"Total errors:         {error_str}")

    rate_color = Colors.GREEN if error_rate < 5 else Colors.YELLOW if error_rate < 10 else Colors.RED
    lines.append(f"Error rate:           {colorize(format_percentage(error_rate, 1), rate_color, color_enabled)}")
    lines.append("")

    # Errors by category (include uncategorized as 'Other')
    cursor = conn.execute(f"""
        SELECT
            COALESCE(error_category, 'Other') as error_category,
            COUNT(*) as count
        FROM tool_calls
        WHERE success = 0
        {date_filter}
        GROUP BY COALESCE(error_category, 'Other')
        ORDER BY count DESC
    """, params)

    category_rows = cursor.fetchall()

    if category_rows:
        lines.append(bold("ERRORS BY CATEGORY", color_enabled))
        lines.append("-" * 40)

        max_cat = max(r['count'] for r in category_rows) if category_rows else 1

        for r in category_rows:
            category = r['error_category'] or 'Other'
            count = r['count']
            bar = create_bar(count, max_cat, width=20)
            pct = (count / total_errors * 100) if total_errors > 0 else 0
            lines.append(f"{category:20} {format_number(count):>5} ({format_percentage(pct, 1):>6}) {bar}")

        lines.append("")

    # Errors by tool
    cursor = conn.execute(f"""
        SELECT
            tool_name,
            COUNT(*) as total,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls
        WHERE 1=1 {date_filter}
        GROUP BY tool_name
        HAVING errors > 0
        ORDER BY errors DESC
        LIMIT 10
    """, params)

    tool_rows = cursor.fetchall()

    if tool_rows:
        lines.append(bold("ERRORS BY TOOL", color_enabled))
        headers = ['Tool', 'Total', 'Errors', 'Rate']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in tool_rows:
            tool = r['tool_name']
            total = r['total']
            errors = r['errors']
            rate = (errors / total * 100) if total > 0 else 0

            rate_str = format_percentage(rate, 1)
            if rate > 10:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)
            elif rate > 5:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)

            table_rows.append([
                tool,
                format_number(total),
                format_number(errors),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # Errors by project
    cursor = conn.execute(f"""
        SELECT
            s.project_display,
            COUNT(*) as total,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls tc
        JOIN sessions s ON s.session_id = tc.session_id
        WHERE 1=1 {date_filter.replace('timestamp', 'tc.timestamp')}
        GROUP BY s.project_display
        HAVING errors > 0
        ORDER BY errors DESC
        LIMIT 5
    """, params)

    project_rows = cursor.fetchall()

    if project_rows:
        lines.append(bold("TOP ERROR PROJECTS", color_enabled))
        lines.append("-" * 40)

        for r in project_rows:
            project = r['project_display'] or 'Unknown'
            if len(project) > 30:
                project = project[:27] + '...'
            errors = r['errors']
            total = r['total']
            rate = (errors / total * 100) if total > 0 else 0
            lines.append(f"{project:30} {format_number(errors):>5} errors ({format_percentage(rate, 1)})")

        lines.append("")

    # Recent errors with messages
    cursor = conn.execute(f"""
        SELECT
            tc.timestamp,
            tc.tool_name,
            tc.error_message,
            s.project_display
        FROM tool_calls tc
        JOIN sessions s ON s.session_id = tc.session_id
        WHERE tc.success = 0
        {date_filter.replace('timestamp', 'tc.timestamp')}
        ORDER BY tc.timestamp DESC
        LIMIT 10
    """, params)

    recent_rows = cursor.fetchall()

    if recent_rows:
        lines.append(bold("RECENT ERRORS", color_enabled))
        lines.append("-" * 60)

        for r in recent_rows:
            timestamp = r['timestamp']
            if timestamp:
                try:
                    dt = datetime.fromisoformat(timestamp.replace('Z', '+00:00'))
                    time_str = dt.strftime('%m-%d %H:%M')
                except:
                    time_str = timestamp[:10]
            else:
                time_str = 'Unknown'

            tool = r['tool_name'] or 'Unknown'
            project = r['project_display'] or 'Unknown'
            if len(project) > 20:
                project = project[:17] + '...'

            error_msg = r['error_message'] or 'No message'
            if len(error_msg) > 50:
                error_msg = error_msg[:47] + '...'

            lines.append(f"{time_str} [{tool:10}] {project:15} {error_msg}")

        lines.append("")

    # Errors by CC version
    cursor = conn.execute(f"""
        SELECT
            COALESCE(s.cc_version, 'unknown') as cc_version,
            COUNT(tc.id) as tool_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls tc
        JOIN sessions s ON s.session_id = tc.session_id
        WHERE 1=1 {date_filter.replace('timestamp', 'tc.timestamp')}
        GROUP BY COALESCE(s.cc_version, 'unknown')
        HAVING errors > 0
        ORDER BY errors DESC
    """, params)

    version_rows = cursor.fetchall()

    if version_rows:
        lines.append(bold("ERRORS BY CC VERSION", color_enabled))
        headers = ['CC Version', 'Tool Calls', 'Errors', 'Error Rate']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in version_rows:
            version = r['cc_version']
            calls = r['tool_calls']
            errors = r['errors']
            rate = (errors / calls * 100) if calls > 0 else 0

            rate_str = format_percentage(rate, 1)
            if rate >= 10:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)
            elif rate >= 5:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)
            else:
                rate_str = colorize(rate_str, Colors.GREEN, color_enabled)

            table_rows.append([
                version,
                format_number(calls),
                format_number(errors),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # Errors by model
    cursor = conn.execute(f"""
        SELECT
            COALESCE(t.model, 'unknown') as model,
            COUNT(tc.id) as tool_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors
        FROM tool_calls tc
        JOIN turns t ON t.id = tc.turn_id
        WHERE 1=1 {date_filter.replace('timestamp', 'tc.timestamp')}
        GROUP BY COALESCE(t.model, 'unknown')
        HAVING errors > 0
        ORDER BY errors DESC
    """, params)

    model_rows = cursor.fetchall()

    if model_rows:
        lines.append(bold("ERRORS BY MODEL", color_enabled))
        headers = ['Model', 'Tool Calls', 'Errors', 'Error Rate']
        alignments = ['l', 'r', 'r', 'r']
        table_rows = []

        for r in model_rows:
            model = r['model']
            display_name = model.replace('claude-', '').replace('-20251101', '').replace('-20250514', '').replace('-20241022', '').replace('-20250929', '')
            calls = r['tool_calls']
            errors = r['errors']
            rate = (errors / calls * 100) if calls > 0 else 0

            rate_str = format_percentage(rate, 1)
            if rate >= 10:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)
            elif rate >= 5:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)
            else:
                rate_str = colorize(rate_str, Colors.GREEN, color_enabled)

            table_rows.append([
                display_name,
                format_number(calls),
                format_number(errors),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    return '\n'.join(lines)
