"""Experiment tag query module."""

from typing import Optional, List, Dict, Any

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter


async def get_tags(db: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """Get all experiment tags with session counts."""
    cursor = await db.execute("""
        SELECT
            tag_name,
            COUNT(*) as session_count,
            MIN(created_at) as created_at
        FROM experiment_tags
        GROUP BY tag_name
        ORDER BY created_at DESC
    """)
    rows = await cursor.fetchall()

    return [
        {
            "tag_name": row[0],
            "session_count": row[1] or 0,
            "created_at": row[2],
        }
        for row in rows
    ]


async def create_tag(
    db: aiosqlite.Connection,
    tag_name: str,
    session_ids: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    project_path: Optional[str] = None,
) -> int:
    """
    Create/assign experiment tags to sessions.

    Tags can be assigned by:
    - Explicit session IDs
    - Date range (all sessions in range)
    - Project path filter

    Returns number of sessions tagged.
    """
    if session_ids:
        # Tag specific sessions
        tagged = 0
        for sid in session_ids:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO experiment_tags (tag_name, session_id) VALUES (?, ?)",
                    (tag_name, sid)
                )
                tagged += 1
            except Exception:
                pass
        await db.commit()
        return tagged

    # Tag by date range and/or project
    params: list = []
    filters = ""
    date_filter = build_date_filter("first_timestamp", date_from, date_to, params)
    filters += date_filter
    if project_path:
        filters += " AND (project_path LIKE ? OR project_display LIKE ?)"
        params.extend([f"%{project_path}%", f"%{project_path}%"])

    cursor = await db.execute(f"""
        SELECT session_id FROM sessions
        WHERE first_timestamp IS NOT NULL {filters}
    """, params)
    rows = await cursor.fetchall()

    tagged = 0
    for row in rows:
        try:
            await db.execute(
                "INSERT OR IGNORE INTO experiment_tags (tag_name, session_id) VALUES (?, ?)",
                (tag_name, row[0])
            )
            tagged += 1
        except Exception:
            pass

    await db.commit()
    return tagged


async def delete_tag(db: aiosqlite.Connection, tag_name: str) -> int:
    """Delete all instances of a tag. Returns count of deleted rows."""
    cursor = await db.execute(
        "DELETE FROM experiment_tags WHERE tag_name = ?",
        (tag_name,)
    )
    await db.commit()
    return cursor.rowcount


async def compare_tags_multi(
    db: aiosqlite.Connection,
    tag_names: List[str],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Compare 2-4 tags across metrics.
    Returns: list of dicts, each with tag_name, sessions, cost, loc, turns, error_rate."""

    async def _get_tag_summary(tag_name: str) -> Dict[str, Any]:
        # Get session IDs for this tag
        cursor = await db.execute(
            "SELECT session_id FROM experiment_tags WHERE tag_name = ?",
            (tag_name,)
        )
        rows = await cursor.fetchall()
        session_ids = [r[0] for r in rows]

        if not session_ids:
            return {
                "tag_name": tag_name,
                "sessions": 0, "cost": 0.0, "loc": 0,
                "turns": 0, "error_rate": 0.0,
            }

        placeholders = ",".join("?" for _ in session_ids)

        # Apply date filters on sessions
        params = list(session_ids)
        date_filters = build_date_filter("s.first_timestamp", date_from, date_to, params)

        # Get filtered session IDs
        cursor = await db.execute(f"""
            SELECT s.session_id
            FROM sessions s
            WHERE s.session_id IN ({placeholders}) {date_filters}
        """, params)
        filtered_rows = await cursor.fetchall()
        filtered_ids = [r[0] for r in filtered_rows]

        if not filtered_ids:
            return {
                "tag_name": tag_name,
                "sessions": 0, "cost": 0.0, "loc": 0,
                "turns": 0, "error_rate": 0.0,
            }

        fp = ",".join("?" for _ in filtered_ids)

        # Query 1: Turn aggregates (separate from tool_calls)
        cursor = await db.execute(f"""
            SELECT
                COUNT(DISTINCT session_id) as sessions,
                SUM(cost) as cost,
                COUNT(*) as turns
            FROM turns
            WHERE session_id IN ({fp})
        """, filtered_ids)
        t_row = await cursor.fetchone()

        # Query 2: Tool call aggregates (separate query)
        cursor = await db.execute(f"""
            SELECT
                COUNT(*) as tool_calls,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
                SUM(loc_written) as loc_written
            FROM tool_calls
            WHERE session_id IN ({fp})
        """, filtered_ids)
        tc_row = await cursor.fetchone()

        tool_calls = tc_row[0] or 0
        errors = tc_row[1] or 0

        return {
            "tag_name": tag_name,
            "sessions": t_row[0] or 0,
            "cost": t_row[1] or 0.0,
            "loc": tc_row[2] or 0,
            "turns": t_row[2] or 0,
            "error_rate": errors / tool_calls if tool_calls > 0 else 0.0,
        }

    results = []
    for tag in tag_names:
        summary = await _get_tag_summary(tag)
        results.append(summary)
    return results


async def get_tag_sessions(
    db: aiosqlite.Connection,
    tag_name: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get sessions belonging to a specific tag.
    Returns: list of session dicts with session_id, project_display, start_time, total_cost, turn_count, model_default."""

    # Get session IDs for this tag
    cursor = await db.execute(
        "SELECT session_id FROM experiment_tags WHERE tag_name = ?",
        (tag_name,)
    )
    rows = await cursor.fetchall()
    session_ids = [r[0] for r in rows]

    if not session_ids:
        return []

    placeholders = ",".join("?" for _ in session_ids)

    # Apply date filters
    params = list(session_ids)
    date_filters = build_date_filter("s.first_timestamp", date_from, date_to, params)

    # Get session details
    cursor = await db.execute(f"""
        SELECT
            s.session_id,
            s.project_display,
            s.first_timestamp,
            s.git_branch
        FROM sessions s
        WHERE s.session_id IN ({placeholders}) {date_filters}
        ORDER BY s.first_timestamp DESC
    """, params)
    session_rows = await cursor.fetchall()

    if not session_rows:
        return []

    # For each session, get cost and turn count from turns (separate query)
    result = []
    for srow in session_rows:
        sid = srow[0]
        cursor = await db.execute("""
            SELECT SUM(cost) as total_cost, COUNT(*) as turn_count,
                   MAX(CASE WHEN model IS NOT NULL AND model NOT LIKE '<%' THEN model END) as model_default
            FROM turns
            WHERE session_id = ?
        """, (sid,))
        t_row = await cursor.fetchone()

        result.append({
            "session_id": sid,
            "project_display": srow[1] or sid,
            "start_time": srow[2],
            "total_cost": t_row[0] or 0.0,
            "turn_count": t_row[1] or 0,
            "model_default": t_row[2],
        })

    return result


async def compare_tags(
    db: aiosqlite.Connection,
    tag_a: str,
    tag_b: str,
) -> Dict[str, Any]:
    """
    Compare two experiment tags side by side.

    Uses two-query pattern for each tag to get metrics.
    """
    async def _get_tag_metrics(tag_name: str) -> Dict[str, Any]:
        # Get session IDs for this tag
        cursor = await db.execute(
            "SELECT session_id FROM experiment_tags WHERE tag_name = ?",
            (tag_name,)
        )
        rows = await cursor.fetchall()
        session_ids = [r[0] for r in rows]

        if not session_ids:
            return {
                "sessions": 0, "cost": 0, "messages": 0, "user_turns": 0,
                "loc_written": 0, "error_rate": 0, "input_tokens": 0,
                "output_tokens": 0, "tool_calls": 0, "errors": 0,
            }

        placeholders = ",".join("?" for _ in session_ids)

        # Query 1: Turn aggregates
        cursor = await db.execute(f"""
            SELECT
                COUNT(DISTINCT session_id) as sessions,
                SUM(cost) as cost,
                COUNT(*) as messages,
                COUNT(CASE WHEN entry_type = 'user' THEN 1 END) as user_turns,
                SUM(input_tokens) as input_tokens,
                SUM(output_tokens) as output_tokens
            FROM turns
            WHERE session_id IN ({placeholders})
        """, session_ids)
        row = await cursor.fetchone()

        # Query 2: Tool call aggregates
        cursor = await db.execute(f"""
            SELECT
                COUNT(*) as tool_calls,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
                SUM(loc_written) as loc_written
            FROM tool_calls
            WHERE session_id IN ({placeholders})
        """, session_ids)
        tc_row = await cursor.fetchone()

        tool_calls = tc_row[0] or 0
        errors = tc_row[1] or 0

        return {
            "sessions": row[0] or 0,
            "cost": row[1] or 0.0,
            "messages": row[2] or 0,
            "user_turns": row[3] or 0,
            "input_tokens": row[4] or 0,
            "output_tokens": row[5] or 0,
            "tool_calls": tool_calls,
            "errors": errors,
            "loc_written": tc_row[2] or 0,
            "error_rate": errors / tool_calls if tool_calls > 0 else 0,
        }

    metrics_a = await _get_tag_metrics(tag_a)
    metrics_b = await _get_tag_metrics(tag_b)

    # Build comparison metrics
    metric_defs = [
        ("cost", False),  # lower is better
        ("messages", True),
        ("user_turns", True),
        ("loc_written", True),
        ("error_rate", False),  # lower is better
        ("input_tokens", False),
        ("output_tokens", True),
        ("tool_calls", True),
    ]

    comparisons = []
    for metric_name, higher_is_better in metric_defs:
        a_val = metrics_a.get(metric_name, 0)
        b_val = metrics_b.get(metric_name, 0)
        delta = b_val - a_val
        pct = (delta / a_val * 100) if a_val != 0 else 0

        if higher_is_better:
            is_improvement = delta > 0
        else:
            is_improvement = delta < 0

        comparisons.append({
            "metric_name": metric_name,
            "tag_a_value": a_val,
            "tag_b_value": b_val,
            "absolute_delta": delta,
            "percentage_delta": pct,
            "is_improvement": is_improvement,
        })

    return {
        "tag_a": tag_a,
        "tag_b": tag_b,
        "tag_a_sessions": metrics_a["sessions"],
        "tag_b_sessions": metrics_b["sessions"],
        "metrics": comparisons,
    }
