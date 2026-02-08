"""Heatmap query module."""

from typing import Optional, List, Tuple

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter


async def get_heatmap_data(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    metric: str = "sessions",
) -> Tuple[List[dict], float]:
    """Get heatmap data grouped by day-of-week and hour.

    Metrics: sessions, cost, loc, tool_calls
    SQLite strftime('%w') returns 0=Sunday. Remap to 0=Monday in Python.
    """
    conditions = []
    params = []

    if metric in ("sessions", "cost"):
        # Query turns table for timestamp granularity
        base_table = "turns t JOIN sessions s ON t.session_id = s.session_id"
        if metric == "sessions":
            agg = "COUNT(DISTINCT t.session_id)"
        else:
            agg = "SUM(t.cost)"
        time_col = "t.timestamp"
    elif metric == "loc":
        base_table = "tool_calls tc JOIN sessions s ON tc.session_id = s.session_id"
        agg = "SUM(tc.loc_written)"
        time_col = "tc.timestamp"
    else:  # tool_calls
        base_table = "tool_calls tc JOIN sessions s ON tc.session_id = s.session_id"
        agg = "COUNT(*)"
        time_col = "tc.timestamp"

    date_params: list = []
    date_clause = build_date_filter(time_col, date_from, date_to, date_params)
    if date_clause:
        conditions.append(date_clause.lstrip(" AND "))
        params.extend(date_params)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    query = f"""
        SELECT
            CAST(strftime('%w', {time_col}, 'localtime') AS INTEGER) as dow,
            CAST(strftime('%H', {time_col}, 'localtime') AS INTEGER) as hour,
            {agg} as value
        FROM {base_table}
        {where}
        GROUP BY dow, hour
    """

    cursor = await db.execute(query, params)
    rows = await cursor.fetchall()

    # Remap SQLite dow (0=Sunday) to 0=Monday
    results = []
    max_value = 0.0
    for row in rows:
        sqlite_dow, hour, value = row[0], row[1], float(row[2] or 0)
        # SQLite: 0=Sun, 1=Mon, ..., 6=Sat -> Remap: 0=Mon, 1=Tue, ..., 6=Sun
        day = (sqlite_dow - 1) % 7
        results.append({"day": day, "hour": hour, "value": value})
        if value > max_value:
            max_value = value

    return results, max_value
