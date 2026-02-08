"""Session query module.

Uses the two-query pattern for session replay to avoid cross-product JOIN inflation.
"""

from typing import Optional, Tuple, List, Dict, Any

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter


async def get_sessions(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    project: Optional[str] = None,
    page: int = 1,
    limit: int = 50,
) -> Tuple[List[Dict[str, Any]], int]:
    """Get paginated session list with key stats."""
    params: list = []
    filters = build_date_filter("s.first_timestamp", date_from, date_to, params)

    if project:
        filters += " AND (s.project_path LIKE ? OR s.project_display LIKE ?)"
        params.extend([f"%{project}%", f"%{project}%"])

    # Count total
    count_cursor = await db.execute(f"""
        SELECT COUNT(DISTINCT s.session_id)
        FROM sessions s
        WHERE s.first_timestamp IS NOT NULL {filters}
    """, params)
    total_count = (await count_cursor.fetchone())[0]

    # Query sessions with turn aggregates
    offset = (page - 1) * limit
    query_params = list(params) + [limit, offset]

    cursor = await db.execute(f"""
        SELECT
            s.session_id,
            s.project_path,
            s.project_display,
            s.first_timestamp,
            s.last_timestamp,
            s.duration_seconds,
            s.is_agent,
            s.cc_version,
            s.git_branch,
            SUM(t.cost) as cost,
            COUNT(t.id) as turns,
            COUNT(CASE WHEN t.entry_type = 'user' THEN 1 END) as user_turns,
            (SELECT t2.model FROM turns t2 WHERE t2.session_id = s.session_id
             AND t2.model IS NOT NULL AND t2.model NOT LIKE '<%'
             ORDER BY t2.timestamp DESC LIMIT 1) as model
        FROM sessions s
        LEFT JOIN turns t ON s.session_id = t.session_id
        WHERE s.first_timestamp IS NOT NULL {filters}
        GROUP BY s.session_id
        ORDER BY s.first_timestamp DESC
        LIMIT ? OFFSET ?
    """, query_params)
    rows = await cursor.fetchall()

    sessions = []
    session_ids = []
    for row in rows:
        sid = row[0]
        session_ids.append(sid)
        sessions.append({
            "session_id": sid,
            "project_path": row[1],
            "project_display": row[2],
            "first_timestamp": row[3],
            "last_timestamp": row[4],
            "duration_seconds": row[5] or 0,
            "is_agent": bool(row[6]),
            "cc_version": row[7],
            "git_branch": row[8],
            "cost": row[9] or 0.0,
            "turns": row[10] or 0,
            "user_turns": row[11] or 0,
            "model": row[12],
            "tool_calls": 0,
            "errors": 0,
        })

    # Query 2: Tool call counts per session
    if session_ids:
        placeholders = ",".join("?" for _ in session_ids)
        cursor = await db.execute(f"""
            SELECT
                session_id,
                COUNT(*) as tool_calls,
                SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
            FROM tool_calls
            WHERE session_id IN ({placeholders})
            GROUP BY session_id
        """, session_ids)
        tc_rows = await cursor.fetchall()

        tc_map = {row[0]: (row[1] or 0, row[2] or 0) for row in tc_rows}
        for s in sessions:
            if s["session_id"] in tc_map:
                s["tool_calls"] = tc_map[s["session_id"]][0]
                s["errors"] = tc_map[s["session_id"]][1]

    return sessions, total_count


async def get_session_replay(
    db: aiosqlite.Connection,
    session_id: str,
) -> Optional[Dict[str, Any]]:
    """
    Get full session replay data. TWO-QUERY PATTERN.

    Query 1: All turns for session, ordered by timestamp
    Query 2: All tool_calls for session, grouped by turn_id
    Merge: attach tool_calls list to each turn, compute cumulative cost
    """
    # Get session info
    cursor = await db.execute("""
        SELECT session_id, project_path, project_display, first_timestamp,
               last_timestamp, duration_seconds, cc_version, git_branch, is_agent
        FROM sessions
        WHERE session_id = ?
    """, (session_id,))
    session_row = await cursor.fetchone()

    if not session_row:
        return None

    session = {
        "session_id": session_row[0],
        "project_path": session_row[1],
        "project_display": session_row[2],
        "first_timestamp": session_row[3],
        "last_timestamp": session_row[4],
        "duration_seconds": session_row[5] or 0,
        "cc_version": session_row[6],
        "git_branch": session_row[7],
        "is_agent": bool(session_row[8]),
    }

    # Query 1: All turns
    cursor = await db.execute("""
        SELECT id, uuid, timestamp, entry_type, model,
               input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
               thinking_chars, cost, stop_reason, is_sidechain, is_meta,
               user_prompt_preview
        FROM turns
        WHERE session_id = ?
        ORDER BY timestamp ASC
    """, (session_id,))
    turn_rows = await cursor.fetchall()

    turns = []
    turn_ids = []
    cumulative_cost = 0.0
    cost_by_model: Dict[str, float] = {}
    total_user_turns = 0

    for row in turn_rows:
        turn_id = row[0]
        turn_ids.append(turn_id)
        cost = row[10] or 0.0
        cumulative_cost += cost
        model = row[4]

        if model:
            cost_by_model[model] = cost_by_model.get(model, 0.0) + cost
        if row[3] == "user":
            total_user_turns += 1

        turns.append({
            "uuid": row[1],
            "timestamp": row[2],
            "entry_type": row[3],
            "model": model,
            "input_tokens": row[5] or 0,
            "output_tokens": row[6] or 0,
            "cache_read_tokens": row[7] or 0,
            "cache_write_tokens": row[8] or 0,
            "thinking_chars": row[9] or 0,
            "cost": cost,
            "cumulative_cost": cumulative_cost,
            "stop_reason": row[11],
            "is_sidechain": bool(row[12]),
            "is_meta": bool(row[13]),
            "user_prompt_preview": row[14],
            "tool_calls": [],
            "_turn_id": turn_id,
        })

    # Query 2: All tool calls for this session
    tool_distribution: Dict[str, int] = {}
    total_errors = 0

    if turn_ids:
        placeholders = ",".join("?" for _ in turn_ids)
        cursor = await db.execute(f"""
            SELECT turn_id, tool_name, file_path, success, error_message,
                   error_category, loc_written, lines_added, lines_deleted, language
            FROM tool_calls
            WHERE turn_id IN ({placeholders})
            ORDER BY id ASC
        """, turn_ids)
        tc_rows = await cursor.fetchall()

        # Build turn_id -> tool_calls mapping
        tc_by_turn: Dict[int, list] = {}
        for row in tc_rows:
            tid = row[0]
            tool_name = row[1]
            success = bool(row[3])

            tool_distribution[tool_name] = tool_distribution.get(tool_name, 0) + 1
            if not success:
                total_errors += 1

            tc = {
                "tool_name": tool_name,
                "file_path": row[2],
                "success": success,
                "error_message": row[4],
                "error_category": row[5],
                "loc_written": row[6] or 0,
                "lines_added": row[7] or 0,
                "lines_deleted": row[8] or 0,
                "language": row[9],
            }
            tc_by_turn.setdefault(tid, []).append(tc)

        # Attach tool calls to turns
        for turn in turns:
            tid = turn.pop("_turn_id")
            turn["tool_calls"] = tc_by_turn.get(tid, [])
    else:
        for turn in turns:
            turn.pop("_turn_id", None)

    total_tool_calls = sum(tool_distribution.values())

    session.update({
        "total_cost": cumulative_cost,
        "total_turns": len(turns),
        "total_user_turns": total_user_turns,
        "total_tool_calls": total_tool_calls,
        "total_errors": total_errors,
        "cost_by_model": cost_by_model,
        "tool_distribution": tool_distribution,
        "turns": turns,
    })

    return session
