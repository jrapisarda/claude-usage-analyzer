"""
Languages report for CCWAP.

Generates the --languages view with LOC by programming language.
FIXES BUG 9: LOC tracked per-tool-call with specific file_path.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage,
    format_table, bold, colorize, Colors, create_bar
)


def generate_languages(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate LOC breakdown by programming language.

    FIXES BUG 9: Each tool call tracks its file path, enabling
    accurate per-language LOC attribution instead of even distribution.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("LOC BY LANGUAGE", color_enabled))

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

    # Query LOC by language
    cursor = conn.execute(f"""
        SELECT
            language,
            SUM(loc_written) as loc_written,
            SUM(lines_added) as lines_added,
            SUM(lines_deleted) as lines_deleted,
            COUNT(DISTINCT file_path) as files,
            COUNT(*) as operations
        FROM tool_calls
        WHERE language IS NOT NULL
        AND language != ''
        AND loc_written > 0
        {date_filter}
        GROUP BY language
        ORDER BY loc_written DESC
    """, params)

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo language data found."

    # Find max LOC for bar chart
    max_loc = max(r['loc_written'] for r in rows)
    total_loc = sum(r['loc_written'] for r in rows)

    # Prepare table data
    headers = ['Language', 'LOC', '%', 'Files', '+Lines', '-Lines', 'Bar']
    alignments = ['l', 'r', 'r', 'r', 'r', 'r', 'l']
    table_rows = []

    for r in rows:
        language = r['language']
        loc = r['loc_written']
        files = r['files'] or 0
        added = r['lines_added'] or 0
        deleted = r['lines_deleted'] or 0

        # Calculate percentage of total
        pct = (loc / total_loc * 100) if total_loc > 0 else 0

        bar = create_bar(loc, max_loc, width=15)

        # Color format added/deleted
        added_str = format_number(added)
        deleted_str = format_number(deleted)
        if added > 0:
            added_str = colorize(f"+{added_str}", Colors.GREEN, color_enabled)
        if deleted > 0:
            deleted_str = colorize(f"-{deleted_str}", Colors.RED, color_enabled)

        table_rows.append([
            language,
            format_number(loc),
            format_percentage(pct, 1),
            format_number(files),
            added_str,
            deleted_str,
            bar,
        ])

    # Add totals row
    total_files = sum(r['files'] or 0 for r in rows)
    total_added = sum(r['lines_added'] or 0 for r in rows)
    total_deleted = sum(r['lines_deleted'] or 0 for r in rows)

    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_number(total_loc), color_enabled),
        bold('100.0%', color_enabled),
        bold(format_number(total_files), color_enabled),
        bold(f"+{format_number(total_added)}", color_enabled),
        bold(f"-{format_number(total_deleted)}", color_enabled),
        '',
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # Net change summary
    lines.append("")
    net_change = total_added - total_deleted
    if net_change >= 0:
        net_str = colorize(f"+{format_number(net_change)}", Colors.GREEN, color_enabled)
    else:
        net_str = colorize(f"{format_number(net_change)}", Colors.RED, color_enabled)
    lines.append(f"Net line change: {net_str}")

    return '\n'.join(lines)
