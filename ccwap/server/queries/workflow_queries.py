"""Workflow analysis query module."""

from collections import Counter
from typing import Optional, List, Dict, Any

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter


async def get_user_type_breakdown(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Human vs agent session/cost breakdown."""
    conditions = []
    params = []
    date_params: list = []
    date_clause = build_date_filter("s.first_timestamp", date_from, date_to, date_params)
    if date_clause:
        conditions.append(date_clause.lstrip(" AND "))
        params.extend(date_params)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'human' END as user_type,
            COUNT(*) as sessions,
            COALESCE(SUM(turn_agg.cost), 0) as total_cost,
            COALESCE(SUM(turn_agg.turns), 0) as total_turns
        FROM sessions s
        LEFT JOIN (
            SELECT session_id, SUM(cost) as cost, COUNT(*) as turns
            FROM turns
            GROUP BY session_id
        ) turn_agg ON turn_agg.session_id = s.session_id
        {where}
        GROUP BY user_type
        ORDER BY sessions DESC
    """
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [{
        "user_type": r[0],
        "sessions": r[1],
        "total_cost": round(float(r[2] or 0), 6),
        "total_turns": int(r[3] or 0),
    } for r in rows]


async def get_user_type_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daily user type trend."""
    conditions = []
    params = []
    date_params: list = []
    date_clause = build_date_filter("s.first_timestamp", date_from, date_to, date_params)
    if date_clause:
        conditions.append(date_clause.lstrip(" AND "))
        params.extend(date_params)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            date(s.first_timestamp, 'localtime') as date,
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'human' END as user_type,
            COUNT(*) as sessions,
            COALESCE(SUM(turn_agg.cost), 0) as cost
        FROM sessions s
        LEFT JOIN (
            SELECT session_id, SUM(cost) as cost
            FROM turns
            GROUP BY session_id
        ) turn_agg ON turn_agg.session_id = s.session_id
        {where}
        GROUP BY date(s.first_timestamp, 'localtime'), user_type
        ORDER BY date(s.first_timestamp, 'localtime')
    """
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [{
        "date": r[0],
        "user_type": r[1],
        "sessions": r[2],
        "cost": round(float(r[3] or 0), 6),
    } for r in rows]


async def get_agent_trees(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Build parent-child session trees from parent_session_id."""
    conditions = []
    params = []
    date_params: list = []
    date_clause = build_date_filter("s.first_timestamp", date_from, date_to, date_params)
    if date_clause:
        conditions.append(date_clause.lstrip(" AND "))
        params.extend(date_params)
    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            s.session_id,
            s.parent_session_id,
            s.project_display,
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'human' END as user_type,
            COALESCE((SELECT SUM(t.cost) FROM turns t
                      WHERE t.session_id = s.session_id), 0) as total_cost
        FROM sessions s
        {where}
        ORDER BY s.first_timestamp
    """
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    # Build tree iteratively
    nodes = {}
    for r in rows:
        nodes[r[0]] = {
            "session_id": r[0],
            "parent_session_id": r[1],
            "project_display": r[2] or "unknown",
            "user_type": r[3],
            "total_cost": round(float(r[4] or 0), 6),
            "children": [],
        }

    roots = []
    for sid, node in list(nodes.items()):
        parent_id = node.get("parent_session_id")
        del node["parent_session_id"]
        if parent_id and parent_id in nodes:
            nodes[parent_id]["children"].append(node)
        else:
            roots.append(node)

    # Only return trees that have children (agent spawns)
    return [r for r in roots if len(r["children"]) > 0][:20]


async def get_tool_sequences(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    window: int = 3,
) -> List[Dict[str, Any]]:
    """Find top tool call sequences using per-session sliding windows."""
    conditions = []
    params = []
    date_params: list = []
    date_clause = build_date_filter("s.first_timestamp", date_from, date_to, date_params)
    if date_clause:
        conditions.append(date_clause.lstrip(" AND "))
        params.extend(date_params)
    extra_where = f"AND {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT tc.session_id, tc.tool_name
        FROM tool_calls tc
        JOIN sessions s ON tc.session_id = s.session_id
        WHERE tc.tool_name IS NOT NULL {extra_where}
        ORDER BY tc.session_id, tc.timestamp
        LIMIT 10000
    """
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    # Build ordered tool lists per session so windows never cross session boundaries.
    session_tools: Dict[str, List[str]] = {}
    for row in rows:
        session_id = row[0]
        tool_name = row[1]
        session_tools.setdefault(session_id, []).append(tool_name)

    # Sliding window within each session.
    counter: Counter = Counter()
    for tools in session_tools.values():
        if len(tools) < window:
            continue
        for i in range(len(tools) - window + 1):
            seq = tuple(tools[i:i + window])
            counter[seq] += 1

    total = sum(counter.values()) or 1
    top = counter.most_common(10)

    return [{
        "sequence": list(seq),
        "count": count,
        "pct": round(count / total * 100, 1),
    } for seq, count in top]
