"""Project detail query module.

Uses separate queries to avoid cross-products between
sessions, turns, and tool_calls.
"""

from typing import Optional, Dict, Any

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter


async def get_project_detail(
    db: aiosqlite.Connection,
    project_path: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Get detailed project data, filtering by activity timestamps in-range."""
    turn_date_params: list = []
    turn_date_filter = build_date_filter("t.timestamp", date_from, date_to, turn_date_params)
    tool_date_params: list = []
    tool_date_filter = build_date_filter("tc.timestamp", date_from, date_to, tool_date_params)

    # Query 1: Session summary + sessions list
    # Candidate sessions are those with turns/tool calls in the requested range.
    session_query = f"""
        WITH turn_agg AS (
            SELECT
                t.session_id,
                SUM(t.cost) AS total_cost,
                COUNT(*) AS turn_count,
                MAX(t.timestamp) AS last_turn_ts
            FROM turns t
            JOIN sessions s ON s.session_id = t.session_id
            WHERE s.project_path = ? {turn_date_filter}
            GROUP BY t.session_id
        ),
        tool_agg AS (
            SELECT
                tc.session_id,
                SUM(tc.loc_written) AS loc_written,
                MAX(tc.timestamp) AS last_tool_ts
            FROM tool_calls tc
            JOIN sessions s ON s.session_id = tc.session_id
            WHERE s.project_path = ? {tool_date_filter}
            GROUP BY tc.session_id
        ),
        candidate_sessions AS (
            SELECT session_id FROM turn_agg
            UNION
            SELECT session_id FROM tool_agg
        )
        SELECT
            s.session_id,
            s.project_display,
            s.first_timestamp,
            COALESCE(ta.total_cost, 0) AS total_cost,
            COALESCE(ta.turn_count, 0) AS turn_count,
            COALESCE(tca.loc_written, 0) AS loc_written,
            (SELECT t.model FROM turns t WHERE t.session_id = s.session_id
             AND t.model IS NOT NULL AND t.model NOT LIKE '<%'
             ORDER BY t.timestamp DESC LIMIT 1) AS model_default,
            s.git_branch,
            COALESCE(ta.last_turn_ts, tca.last_tool_ts, s.first_timestamp) AS last_activity_ts
        FROM sessions s
        JOIN candidate_sessions cs ON cs.session_id = s.session_id
        LEFT JOIN turn_agg ta ON ta.session_id = s.session_id
        LEFT JOIN tool_agg tca ON tca.session_id = s.session_id
        ORDER BY last_activity_ts DESC
    """
    session_params = [project_path, *turn_date_params, project_path, *tool_date_params]
    cursor = await db.execute(session_query, session_params)
    session_rows = await cursor.fetchall()

    if not session_rows:
        return None

    project_display = session_rows[0][1] or project_path
    total_cost = sum(float(r[3] or 0) for r in session_rows)
    total_sessions = len(session_rows)
    total_loc = sum(int(r[5] or 0) for r in session_rows)

    sessions = [{
        "session_id": r[0],
        "start_time": r[2] or "",
        "total_cost": round(float(r[3] or 0), 6),
        "turn_count": int(r[4] or 0),
        "loc_written": int(r[5] or 0),
        "model_default": r[6],
    } for r in session_rows[:50]]

    # Query 2: Cost trend by activity date
    cost_query = f"""
        SELECT
            date(t.timestamp, 'localtime') AS date,
            COALESCE(SUM(t.cost), 0) AS cost
        FROM turns t
        JOIN sessions s ON s.session_id = t.session_id
        WHERE s.project_path = ? {turn_date_filter}
        GROUP BY date(t.timestamp, 'localtime')
        ORDER BY date(t.timestamp, 'localtime')
    """
    cost_params = [project_path, *turn_date_params]
    cursor = await db.execute(cost_query, cost_params)
    cost_rows = await cursor.fetchall()
    cost_trend = [{"date": r[0], "cost": round(float(r[1] or 0), 6)} for r in cost_rows]

    # Query 3: Languages from tool_calls (activity in range)
    lang_query = f"""
        SELECT
            COALESCE(tc.language, 'unknown') AS language,
            SUM(tc.loc_written) AS loc_written
        FROM tool_calls tc
        JOIN sessions s ON s.session_id = tc.session_id
        WHERE s.project_path = ? {tool_date_filter}
            AND tc.language IS NOT NULL
            AND tc.loc_written > 0
        GROUP BY language
        ORDER BY loc_written DESC
        LIMIT 15
    """
    lang_params = [project_path, *tool_date_params]
    cursor = await db.execute(lang_query, lang_params)
    lang_rows = await cursor.fetchall()
    languages = [{"language": r[0], "loc_written": int(r[1] or 0)} for r in lang_rows]

    # Query 4: Tools from tool_calls (activity in range)
    tool_query = f"""
        SELECT
            tc.tool_name,
            COUNT(*) AS count,
            AVG(CASE WHEN tc.success THEN 1.0 ELSE 0.0 END) AS success_rate
        FROM tool_calls tc
        JOIN sessions s ON s.session_id = tc.session_id
        WHERE s.project_path = ? {tool_date_filter}
        GROUP BY tc.tool_name
        ORDER BY count DESC
        LIMIT 15
    """
    tool_params = [project_path, *tool_date_params]
    cursor = await db.execute(tool_query, tool_params)
    tool_rows = await cursor.fetchall()
    tools = [{
        "tool_name": r[0],
        "count": r[1],
        "success_rate": round(float(r[2] or 0), 3),
    } for r in tool_rows]

    # Query 5: Branches (computed from session rows already fetched)
    branch_map: dict = {}
    for r in session_rows:
        branch = r[7] or "unknown"
        if branch not in branch_map:
            branch_map[branch] = {"sessions": 0, "cost": 0.0}
        branch_map[branch]["sessions"] += 1
        branch_map[branch]["cost"] += float(r[3] or 0)
    branches = [
        {"branch": b, "sessions": d["sessions"], "cost": round(d["cost"], 6)}
        for b, d in sorted(branch_map.items(), key=lambda x: -x[1]["cost"])
    ][:10]

    return {
        "project_display": project_display,
        "total_cost": round(total_cost, 6),
        "total_sessions": total_sessions,
        "total_loc": total_loc,
        "cost_trend": cost_trend,
        "languages": languages,
        "tools": tools,
        "branches": branches,
        "sessions": sessions,
    }
