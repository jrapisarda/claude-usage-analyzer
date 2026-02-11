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
    """Get detailed project data. Uses separate queries to avoid cross-products."""
    conditions = ["s.project_path = ?"]
    params = [project_path]
    date_params: list = []
    date_clause = build_date_filter("s.first_timestamp", date_from, date_to, date_params)
    if date_clause:
        conditions.append(date_clause.lstrip(" AND "))
        params.extend(date_params)
    where = f"WHERE {' AND '.join(conditions)}"

    # Query 1: Session summary + sessions list
    session_query = f"""
        SELECT
            s.session_id,
            s.project_display,
            s.first_timestamp,
            COALESCE((SELECT SUM(t.cost) FROM turns t
                      WHERE t.session_id = s.session_id), 0) as total_cost,
            (SELECT COUNT(*) FROM turns t
             WHERE t.session_id = s.session_id) as turn_count,
            COALESCE((SELECT SUM(tc.loc_written) FROM tool_calls tc
                      WHERE tc.session_id = s.session_id), 0) as loc_written,
            (SELECT t.model FROM turns t WHERE t.session_id = s.session_id
             AND t.model IS NOT NULL AND t.model NOT LIKE '<%'
             ORDER BY t.timestamp DESC LIMIT 1) as model_default,
            s.git_branch
        FROM sessions s
        {where}
        ORDER BY s.first_timestamp DESC
    """
    cursor = await db.execute(session_query, params)
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

    # Query 2: Cost trend by date
    cost_query = f"""
        SELECT
            date(s.first_timestamp, 'localtime') as date,
            COALESCE(SUM(turn_agg.cost), 0) as cost
        FROM sessions s
        LEFT JOIN (
            SELECT session_id, SUM(cost) as cost
            FROM turns
            GROUP BY session_id
        ) turn_agg ON turn_agg.session_id = s.session_id
        {where}
        GROUP BY date(s.first_timestamp, 'localtime')
        ORDER BY date(s.first_timestamp, 'localtime')
    """
    cursor = await db.execute(cost_query, params)
    cost_rows = await cursor.fetchall()
    cost_trend = [{"date": r[0], "cost": round(float(r[1] or 0), 6)} for r in cost_rows]

    # Query 3: Languages from tool_calls (separate query)
    session_ids = [r[0] for r in session_rows]
    placeholders = ",".join(["?"] * len(session_ids))
    lang_query = f"""
        SELECT
            COALESCE(tc.language, 'unknown') as language,
            SUM(tc.loc_written) as loc_written
        FROM tool_calls tc
        WHERE tc.session_id IN ({placeholders})
            AND tc.language IS NOT NULL
            AND tc.loc_written > 0
        GROUP BY language
        ORDER BY loc_written DESC
        LIMIT 15
    """
    cursor = await db.execute(lang_query, session_ids)
    lang_rows = await cursor.fetchall()
    languages = [{"language": r[0], "loc_written": int(r[1] or 0)} for r in lang_rows]

    # Query 4: Tools from tool_calls (separate query)
    tool_query = f"""
        SELECT
            tc.tool_name,
            COUNT(*) as count,
            AVG(CASE WHEN tc.success THEN 1.0 ELSE 0.0 END) as success_rate
        FROM tool_calls tc
        WHERE tc.session_id IN ({placeholders})
        GROUP BY tc.tool_name
        ORDER BY count DESC
        LIMIT 15
    """
    cursor = await db.execute(tool_query, session_ids)
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
