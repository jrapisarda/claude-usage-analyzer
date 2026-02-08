"""
Experiment tags for CCWAP.

Handles --tag, --tag-range, and --compare-tags functionality.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens, format_delta,
    format_table, bold, colorize, Colors
)


def tag_sessions(
    conn: sqlite3.Connection,
    tag_name: str,
    session_ids: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None
) -> int:
    """
    Tag sessions with a label.

    Args:
        conn: Database connection
        tag_name: Name of the tag
        session_ids: Specific sessions to tag (or None for all in date range)
        date_from: Start date for tagging
        date_to: End date for tagging

    Returns:
        Number of sessions tagged
    """
    if session_ids:
        # Tag specific sessions
        for session_id in session_ids:
            conn.execute("""
                INSERT OR IGNORE INTO experiment_tags (tag_name, session_id)
                VALUES (?, ?)
            """, (tag_name, session_id))
        conn.commit()
        return len(session_ids)

    # Tag by date range
    if date_from is None:
        date_from = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if date_to is None:
        date_to = datetime.now()

    cursor = conn.execute("""
        SELECT session_id FROM sessions
        WHERE date(first_timestamp) >= date(?)
        AND date(first_timestamp) <= date(?)
    """, (date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))

    sessions = cursor.fetchall()
    for row in sessions:
        conn.execute("""
            INSERT OR IGNORE INTO experiment_tags (tag_name, session_id)
            VALUES (?, ?)
        """, (tag_name, row['session_id']))

    conn.commit()
    return len(sessions)


def list_tags(conn: sqlite3.Connection, color_enabled: bool = True) -> str:
    """List all experiment tags with session counts."""
    lines = []
    lines.append(bold("EXPERIMENT TAGS", color_enabled))
    lines.append("-" * 40)

    cursor = conn.execute("""
        SELECT
            tag_name,
            COUNT(*) as session_count,
            MIN(created_at) as first_tagged,
            MAX(created_at) as last_tagged
        FROM experiment_tags
        GROUP BY tag_name
        ORDER BY last_tagged DESC
    """)

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo tags found."

    for r in rows:
        lines.append(f"{r['tag_name']:30} {format_number(r['session_count']):>5} sessions")

    return '\n'.join(lines)


def compare_tags(
    conn: sqlite3.Connection,
    tag_a: str,
    tag_b: str,
    config: Dict[str, Any],
    color_enabled: bool = True
) -> str:
    """
    Compare two experiment tags.

    Args:
        conn: Database connection
        tag_a: First tag to compare
        tag_b: Second tag to compare
        config: Configuration dict
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold(f"COMPARING: {tag_a} vs {tag_b}", color_enabled))
    lines.append("=" * 60)
    lines.append("")

    # Get stats for each tag
    stats_a = _get_tag_stats(conn, tag_a)
    stats_b = _get_tag_stats(conn, tag_b)

    if not stats_a:
        return f"Tag not found: {tag_a}"
    if not stats_b:
        return f"Tag not found: {tag_b}"

    # Comparison table
    headers = ['Metric', tag_a, tag_b, 'Delta']
    alignments = ['l', 'r', 'r', 'r']
    table_rows = []

    metrics = [
        ('Sessions', 'sessions', format_number),
        ('Turns', 'turns', format_number),
        ('Input Tokens', 'input_tokens', format_tokens),
        ('Output Tokens', 'output_tokens', format_tokens),
        ('Total Cost', 'cost', format_currency),
        ('Avg Cost/Session', 'avg_cost', format_currency),
        ('Tool Calls', 'tool_calls', format_number),
        ('Error Rate', 'error_rate', lambda x: f"{x*100:.1f}%"),
    ]

    for label, key, fmt in metrics:
        val_a = stats_a.get(key, 0)
        val_b = stats_b.get(key, 0)

        if key in ('cost', 'avg_cost'):
            delta = format_delta(val_b, val_a, color_enabled=color_enabled)
        else:
            if val_a > 0:
                pct = ((val_b - val_a) / val_a) * 100
                if pct > 0:
                    delta = colorize(f"+{pct:.1f}%", Colors.RED if key == 'error_rate' else Colors.GREEN, color_enabled)
                elif pct < 0:
                    delta = colorize(f"{pct:.1f}%", Colors.GREEN if key == 'error_rate' else Colors.RED, color_enabled)
                else:
                    delta = "0%"
            else:
                delta = "N/A"

        table_rows.append([label, fmt(val_a), fmt(val_b), delta])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    return '\n'.join(lines)


def _get_tag_stats(conn: sqlite3.Connection, tag_name: str) -> Optional[Dict[str, Any]]:
    """Get aggregated statistics for a tag."""
    cursor = conn.execute("""
        SELECT
            COUNT(DISTINCT et.session_id) as sessions,
            COUNT(t.id) as turns,
            SUM(t.input_tokens) as input_tokens,
            SUM(t.output_tokens) as output_tokens,
            SUM(t.cost) as cost
        FROM experiment_tags et
        JOIN turns t ON t.session_id = et.session_id
        WHERE et.tag_name = ?
    """, (tag_name,))

    row = cursor.fetchone()
    if not row or row['sessions'] == 0:
        return None

    sessions = row['sessions'] or 0
    cost = row['cost'] or 0

    # Get tool call stats
    tc_cursor = conn.execute("""
        SELECT
            COUNT(*) as tool_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors
        FROM experiment_tags et
        JOIN tool_calls tc ON tc.session_id = et.session_id
        WHERE et.tag_name = ?
    """, (tag_name,))

    tc_row = tc_cursor.fetchone()
    tool_calls = tc_row['tool_calls'] or 0
    errors = tc_row['errors'] or 0

    return {
        'sessions': sessions,
        'turns': row['turns'] or 0,
        'input_tokens': row['input_tokens'] or 0,
        'output_tokens': row['output_tokens'] or 0,
        'cost': cost,
        'avg_cost': cost / sessions if sessions > 0 else 0,
        'tool_calls': tool_calls,
        'error_rate': errors / tool_calls if tool_calls > 0 else 0,
    }
