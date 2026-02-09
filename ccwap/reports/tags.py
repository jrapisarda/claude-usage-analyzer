"""
Experiment tags for CCWAP.

Handles --tag, --tag-range, --compare-tags, and --list-tags functionality.
Supports smart tags with stored criteria for dynamic session resolution.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional, List

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens, format_delta,
    format_table, bold, colorize, Colors
)


def _resolve_tag_sessions_sync(
    conn: sqlite3.Connection, tag_name: str
) -> List[str]:
    """
    Resolve all session IDs for a tag (synchronous version).
    1. Evaluate criteria from tag_definitions (dynamic/smart)
    2. UNION with explicit entries from experiment_tags (manual)
    3. Deduplicate
    """
    session_ids: set = set()

    # Step 1: Check tag_definitions for dynamic criteria
    cursor = conn.execute(
        "SELECT * FROM tag_definitions WHERE tag_name = ?", (tag_name,)
    )
    defn = cursor.fetchone()

    if defn:
        params: list = []
        filters: list = []

        # Date range
        if defn['date_from']:
            filters.append("date(s.first_timestamp, 'localtime') >= ?")
            params.append(defn['date_from'])
        if defn['date_to']:
            filters.append("date(s.first_timestamp, 'localtime') <= ?")
            params.append(defn['date_to'])

        # Project path (LIKE match)
        if defn['project_path']:
            filters.append(
                "(s.project_path LIKE ? OR s.project_display LIKE ?)"
            )
            params.extend([f"%{defn['project_path']}%", f"%{defn['project_path']}%"])

        # CC version
        if defn['cc_version']:
            filters.append("s.cc_version LIKE ?")
            params.append(f"%{defn['cc_version']}%")

        where_clause = " AND ".join(filters) if filters else "1=1"
        query = f"""
            SELECT s.session_id FROM sessions s
            WHERE s.first_timestamp IS NOT NULL AND {where_clause}
        """

        # Model filter (subquery into turns)
        if defn['model']:
            query += " AND s.session_id IN (SELECT DISTINCT session_id FROM turns WHERE model LIKE ?)"
            params.append(f"%{defn['model']}%")

        # Cost range (subqueries into turns)
        if defn['min_cost'] is not None:
            query += " AND s.session_id IN (SELECT session_id FROM turns GROUP BY session_id HAVING SUM(cost) >= ?)"
            params.append(defn['min_cost'])
        if defn['max_cost'] is not None:
            query += " AND s.session_id IN (SELECT session_id FROM turns GROUP BY session_id HAVING SUM(cost) <= ?)"
            params.append(defn['max_cost'])

        # LOC range (subqueries into tool_calls)
        if defn['min_loc'] is not None:
            query += " AND s.session_id IN (SELECT session_id FROM tool_calls GROUP BY session_id HAVING SUM(loc_written) >= ?)"
            params.append(defn['min_loc'])
        if defn['max_loc'] is not None:
            query += " AND s.session_id IN (SELECT session_id FROM tool_calls GROUP BY session_id HAVING SUM(loc_written) <= ?)"
            params.append(defn['max_loc'])

        cursor = conn.execute(query, params)
        rows = cursor.fetchall()
        session_ids.update(r['session_id'] for r in rows)

    # Step 2: Add explicit manual session IDs from experiment_tags
    cursor = conn.execute(
        "SELECT session_id FROM experiment_tags WHERE tag_name = ?",
        (tag_name,),
    )
    rows = cursor.fetchall()
    session_ids.update(r['session_id'] for r in rows)

    return list(session_ids)


def tag_sessions(
    conn: sqlite3.Connection,
    tag_name: str,
    session_ids: Optional[List[str]] = None,
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    project: Optional[str] = None,
    cc_version: Optional[str] = None,
    model: Optional[str] = None,
    min_cost: Optional[float] = None,
    max_cost: Optional[float] = None,
    min_loc: Optional[int] = None,
    max_loc: Optional[int] = None,
) -> int:
    """
    Tag sessions with a label.

    Smart mode: if any criteria fields are provided, stores them in
    tag_definitions for dynamic evaluation.
    Manual mode: if only session_ids, inserts into experiment_tags (static).
    """
    has_criteria = any([
        date_from, date_to, project, cc_version, model,
        min_cost is not None, max_cost is not None,
        min_loc is not None, max_loc is not None,
    ])

    if session_ids and not has_criteria:
        # Pure manual mode
        for session_id in session_ids:
            conn.execute("""
                INSERT OR IGNORE INTO experiment_tags (tag_name, session_id)
                VALUES (?, ?)
            """, (tag_name, session_id))
        conn.commit()
        return len(session_ids)

    if has_criteria:
        # Smart tag mode -- store criteria in tag_definitions
        df = date_from.strftime('%Y-%m-%d') if date_from else None
        dt = date_to.strftime('%Y-%m-%d') if date_to else None

        conn.execute("""
            INSERT OR REPLACE INTO tag_definitions
                (tag_name, date_from, date_to, project_path,
                 cc_version, model, min_cost, max_cost, min_loc, max_loc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (tag_name, df, dt, project, cc_version, model,
              min_cost, max_cost, min_loc, max_loc))

        # Also add explicit session_ids if provided alongside criteria
        if session_ids:
            for session_id in session_ids:
                conn.execute("""
                    INSERT OR IGNORE INTO experiment_tags (tag_name, session_id)
                    VALUES (?, ?)
                """, (tag_name, session_id))

        conn.commit()
        sessions = _resolve_tag_sessions_sync(conn, tag_name)
        return len(sessions)

    # Fallback: no criteria, no session_ids -- tag today's sessions (legacy)
    if date_from is None:
        date_from = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
    if date_to is None:
        date_to = datetime.now()

    # Store as smart tag
    conn.execute("""
        INSERT OR REPLACE INTO tag_definitions
            (tag_name, date_from, date_to)
        VALUES (?, ?, ?)
    """, (tag_name, date_from.strftime('%Y-%m-%d'), date_to.strftime('%Y-%m-%d')))
    conn.commit()

    sessions = _resolve_tag_sessions_sync(conn, tag_name)
    return len(sessions)


def list_tags(conn: sqlite3.Connection, color_enabled: bool = True) -> str:
    """List all experiment tags with session counts."""
    lines = []
    lines.append(bold("EXPERIMENT TAGS", color_enabled))
    lines.append("-" * 60)

    # Get all tag names from both tables
    cursor = conn.execute("""
        SELECT tag_name, created_at FROM tag_definitions
        UNION
        SELECT DISTINCT tag_name, MIN(created_at) FROM experiment_tags GROUP BY tag_name
    """)
    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo tags found."

    seen: set = set()
    tag_entries = []
    for r in rows:
        name = r['tag_name']
        if name in seen:
            continue
        seen.add(name)

        sessions = _resolve_tag_sessions_sync(conn, name)
        count = len(sessions)

        # Check if smart
        defn = conn.execute(
            "SELECT tag_name FROM tag_definitions WHERE tag_name = ?", (name,)
        ).fetchone()
        tag_type = colorize("[smart]", Colors.CYAN, color_enabled) if defn else "[static]"

        tag_entries.append((name, count, tag_type))

    for name, count, tag_type in tag_entries:
        lines.append(f"  {name:25} {format_number(count):>5} sessions  {tag_type}")

    return '\n'.join(lines)


def _get_tag_stats(conn: sqlite3.Connection, tag_name: str) -> Optional[Dict[str, Any]]:
    """Get expanded statistics for a tag (16 metrics)."""
    session_ids = _resolve_tag_sessions_sync(conn, tag_name)

    if not session_ids:
        return None

    placeholders = ",".join("?" for _ in session_ids)

    # Query 1: Turn aggregates
    cursor = conn.execute(f"""
        SELECT
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as messages,
            COUNT(CASE WHEN entry_type = 'user' THEN 1 END) as user_turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(cache_write_tokens) as cache_write_tokens,
            SUM(thinking_chars) as thinking_chars,
            SUM(cost) as cost
        FROM turns
        WHERE session_id IN ({placeholders})
    """, session_ids)
    row = cursor.fetchone()

    if not row or row['sessions'] == 0:
        return None

    # Query 2: Tool call aggregates
    tc_cursor = conn.execute(f"""
        SELECT
            COUNT(*) as tool_calls,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
            SUM(loc_written) as loc_written,
            SUM(lines_added) as lines_added,
            SUM(lines_deleted) as lines_deleted,
            COUNT(DISTINCT CASE WHEN tool_name = 'Write' THEN file_path END) as files_created,
            COUNT(DISTINCT CASE WHEN tool_name = 'Edit' THEN file_path END) as files_edited
        FROM tool_calls
        WHERE session_id IN ({placeholders})
    """, session_ids)
    tc_row = tc_cursor.fetchone()

    # Query 3: Agent spawns
    ag_cursor = conn.execute(f"""
        SELECT COUNT(*) as agent_spawns
        FROM sessions
        WHERE session_id IN ({placeholders}) AND is_agent = 1
    """, session_ids)
    ag_row = ag_cursor.fetchone()

    sessions = row['sessions'] or 0
    cost = row['cost'] or 0
    input_tokens = row['input_tokens'] or 0
    output_tokens = row['output_tokens'] or 0
    cache_read = row['cache_read_tokens'] or 0
    tool_calls = tc_row['tool_calls'] or 0
    errors = tc_row['errors'] or 0
    loc_written = tc_row['loc_written'] or 0
    lines_added = tc_row['lines_added'] or 0
    lines_deleted = tc_row['lines_deleted'] or 0

    # Derived
    error_rate = errors / tool_calls if tool_calls > 0 else 0
    loc_delivered = lines_added - lines_deleted
    cache_denom = input_tokens + cache_read
    cache_hit_rate = cache_read / cache_denom if cache_denom > 0 else 0
    cost_per_kloc = (cost / (loc_written / 1000)) if loc_written > 0 else 0
    tokens_per_loc = (input_tokens + output_tokens) / loc_written if loc_written > 0 else 0

    return {
        'sessions': sessions,
        'cost': cost,
        'user_turns': row['user_turns'] or 0,
        'input_tokens': input_tokens,
        'output_tokens': output_tokens,
        'cache_read_tokens': cache_read,
        'thinking_chars': row['thinking_chars'] or 0,
        'tool_calls': tool_calls,
        'error_rate': error_rate,
        'loc_written': loc_written,
        'loc_delivered': loc_delivered,
        'files_created': tc_row['files_created'] or 0,
        'files_edited': tc_row['files_edited'] or 0,
        'agent_spawns': ag_row['agent_spawns'] or 0,
        'cache_hit_rate': cache_hit_rate,
        'cost_per_kloc': cost_per_kloc,
        'tokens_per_loc': tokens_per_loc,
    }


def compare_tags(
    conn: sqlite3.Connection,
    tag_a: str,
    tag_b: str,
    config: Dict[str, Any],
    color_enabled: bool = True
) -> str:
    """Compare two experiment tags with expanded grouped metrics."""
    lines = []
    lines.append(bold(f"COMPARING: {tag_a} vs {tag_b}", color_enabled))
    lines.append("=" * 70)
    lines.append("")

    stats_a = _get_tag_stats(conn, tag_a)
    stats_b = _get_tag_stats(conn, tag_b)

    if not stats_a:
        return f"Tag not found or empty: {tag_a}"
    if not stats_b:
        return f"Tag not found or empty: {tag_b}"

    # Grouped metric definitions: (label, key, formatter, is_lower_better)
    categories = [
        ("COST & EFFICIENCY", [
            ('Total Cost', 'cost', format_currency, True),
            ('Cost/KLOC', 'cost_per_kloc', format_currency, True),
            ('Cache Hit Rate', 'cache_hit_rate', lambda x: f"{x*100:.1f}%", False),
        ]),
        ("PRODUCTIVITY", [
            ('LOC Written', 'loc_written', format_number, False),
            ('LOC Delivered', 'loc_delivered', format_number, False),
            ('Files Created', 'files_created', format_number, False),
            ('Files Edited', 'files_edited', format_number, False),
        ]),
        ("TOKENS", [
            ('Input Tokens', 'input_tokens', format_tokens, True),
            ('Output Tokens', 'output_tokens', format_tokens, False),
            ('Tokens/LOC', 'tokens_per_loc', format_number, True),
            ('Thinking Chars', 'thinking_chars', format_tokens, False),
        ]),
        ("QUALITY & WORKFLOW", [
            ('Sessions', 'sessions', format_number, False),
            ('User Turns', 'user_turns', format_number, False),
            ('Tool Calls', 'tool_calls', format_number, False),
            ('Error Rate', 'error_rate', lambda x: f"{x*100:.1f}%", True),
            ('Agent Spawns', 'agent_spawns', format_number, False),
        ]),
    ]

    headers = ['Metric', tag_a, tag_b, 'Delta']
    alignments = ['l', 'r', 'r', 'r']

    for cat_name, metrics in categories:
        lines.append(f"  {bold(cat_name, color_enabled)}")
        lines.append(f"  {'-' * 66}")

        table_rows = []
        for label, key, fmt, is_lower_better in metrics:
            val_a = stats_a.get(key, 0)
            val_b = stats_b.get(key, 0)

            if key in ('cost', 'cost_per_kloc'):
                delta = format_delta(val_b, val_a, color_enabled=color_enabled)
            elif key in ('error_rate', 'cache_hit_rate'):
                if val_a > 0:
                    pct = ((val_b - val_a) / val_a) * 100
                    if is_lower_better:
                        color = Colors.GREEN if pct < 0 else Colors.RED
                    else:
                        color = Colors.GREEN if pct > 0 else Colors.RED
                    sign = "+" if pct > 0 else ""
                    delta = colorize(f"{sign}{pct:.1f}%", color, color_enabled)
                else:
                    delta = "N/A"
            else:
                if val_a > 0:
                    pct = ((val_b - val_a) / val_a) * 100
                    if is_lower_better:
                        color = Colors.GREEN if pct < 0 else Colors.RED
                    else:
                        color = Colors.GREEN if pct > 0 else Colors.RED
                    sign = "+" if pct > 0 else ""
                    delta = colorize(f"{sign}{pct:.1f}%", color, color_enabled)
                else:
                    delta = "N/A"

            table_rows.append([label, fmt(val_a), fmt(val_b), delta])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    return '\n'.join(lines)
