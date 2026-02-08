"""Model comparison query module.

Uses the two-query pattern: query sessions separately from turns
to avoid N*M cross-product inflation.
"""

from typing import Optional, List, Dict, Any

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter


async def get_model_metrics(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Per-model aggregated metrics using two separate queries."""
    conditions = ["t.model IS NOT NULL", "t.model NOT LIKE '<%'"]
    params = []
    date_params: list = []
    date_clause = build_date_filter("t.timestamp", date_from, date_to, date_params)
    if date_clause:
        conditions.append(date_clause.lstrip(" AND "))
        params.extend(date_params)
    where = f"WHERE {' AND '.join(conditions)}"

    # Query 1: Turn-level aggregates by model
    turn_query = f"""
        SELECT
            t.model,
            COUNT(DISTINCT t.session_id) as sessions,
            COUNT(*) as turns,
            SUM(t.cost) as total_cost,
            AVG(t.cost) as avg_turn_cost,
            SUM(t.input_tokens) as total_input_tokens,
            SUM(t.output_tokens) as total_output_tokens,
            AVG(t.thinking_chars) as avg_thinking_chars
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        {where}
        GROUP BY t.model
        ORDER BY total_cost DESC
    """
    cursor = await db.execute(turn_query, params)
    turn_rows = await cursor.fetchall()

    # Query 2: LOC by model (from tool_calls, separate to avoid cross-product)
    loc_conditions = ["t.model IS NOT NULL", "t.model NOT LIKE '<%'"]
    loc_params = []
    loc_date_params: list = []
    loc_date_clause = build_date_filter("tc.timestamp", date_from, date_to, loc_date_params)
    if loc_date_clause:
        loc_conditions.append(loc_date_clause.lstrip(" AND "))
        loc_params.extend(loc_date_params)
    loc_where = f"WHERE {' AND '.join(loc_conditions)}"
    loc_query = f"""
        SELECT
            t.model,
            SUM(tc.loc_written) as loc_written
        FROM tool_calls tc
        JOIN turns t ON tc.turn_id = t.id
        JOIN sessions s ON tc.session_id = s.session_id
        {loc_where}
        GROUP BY t.model
    """
    cursor2 = await db.execute(loc_query, loc_params)
    loc_rows = await cursor2.fetchall()
    loc_map = {r[0]: int(r[1] or 0) for r in loc_rows}

    results = []
    for row in turn_rows:
        model = row[0] or "unknown"
        results.append({
            "model": model,
            "sessions": row[1],
            "turns": row[2],
            "total_cost": round(float(row[3] or 0), 6),
            "avg_turn_cost": round(float(row[4] or 0), 6),
            "total_input_tokens": int(row[5] or 0),
            "total_output_tokens": int(row[6] or 0),
            "avg_thinking_chars": round(float(row[7] or 0), 1),
            "loc_written": loc_map.get(model, 0),
        })
    return results


async def get_model_usage_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daily model usage counts."""
    conditions = ["t.model IS NOT NULL", "t.model NOT LIKE '<%'"]
    params = []
    date_params: list = []
    date_clause = build_date_filter("t.timestamp", date_from, date_to, date_params)
    if date_clause:
        conditions.append(date_clause.lstrip(" AND "))
        params.extend(date_params)
    where = f"WHERE {' AND '.join(conditions)}"

    query = f"""
        SELECT
            DATE(t.timestamp) as date,
            t.model,
            COUNT(*) as count
        FROM turns t
        {where}
        GROUP BY date, t.model
        ORDER BY date
    """
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [{"date": r[0], "model": r[1], "count": r[2]} for r in rows]


async def get_model_scatter(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Per-session cost vs LOC by model for scatter plot."""
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
            (SELECT t.model FROM turns t WHERE t.session_id = s.session_id
             AND t.model IS NOT NULL AND t.model NOT LIKE '<%'
             ORDER BY t.timestamp DESC LIMIT 1) as model,
            COALESCE((SELECT SUM(t.cost) FROM turns t
                      WHERE t.session_id = s.session_id), 0) as total_cost,
            COALESCE((SELECT SUM(tc.loc_written) FROM tool_calls tc
                      WHERE tc.session_id = s.session_id), 0) as loc_written
        FROM sessions s
        {where}
        ORDER BY total_cost DESC
        LIMIT 200
    """
    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()
    return [{
        "session_id": r[0],
        "model": r[1] or "unknown",
        "cost": round(float(r[2] or 0), 6),
        "loc_written": int(r[3] or 0),
    } for r in rows if r[1]]
