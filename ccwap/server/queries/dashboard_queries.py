"""Dashboard query module.

Uses the two-query pattern: separate turns and tool_calls queries to avoid
cross-product JOIN inflation.
"""

from datetime import date, timedelta
from typing import Any, Dict, List, Optional

import aiosqlite

from ccwap.server.queries.date_helpers import local_today, build_date_filter, build_summary_filter


async def get_vitals_today(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> dict:
    """Get key metrics from turns + tool_calls (two queries).

    When no date range provided, defaults to today (local time).
    """
    if not date_from and not date_to:
        date_from = date_to = local_today()

    # Query 1: Turns aggregates
    params: list = []
    date_filter = build_date_filter("timestamp", date_from, date_to, params)
    cursor = await db.execute(f"""
        SELECT
            COUNT(DISTINCT session_id) as sessions,
            COUNT(*) as messages,
            COUNT(CASE WHEN entry_type = 'user' THEN 1 END) as user_turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cost) as cost
        FROM turns
        WHERE timestamp IS NOT NULL {date_filter}
    """, params)
    row = await cursor.fetchone()
    sessions = row[0] or 0
    messages = row[1] or 0
    user_turns = row[2] or 0
    input_tokens = row[3] or 0
    output_tokens = row[4] or 0
    cost = row[5] or 0.0

    # Query 2: Tool calls aggregates
    tc_params: list = []
    tc_date_filter = build_date_filter("timestamp", date_from, date_to, tc_params)
    cursor = await db.execute(f"""
        SELECT
            COUNT(*) as tool_calls,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
            SUM(loc_written) as loc_written
        FROM tool_calls
        WHERE timestamp IS NOT NULL {tc_date_filter}
    """, tc_params)
    row = await cursor.fetchone()
    tool_calls = row[0] or 0
    errors = row[1] or 0
    loc_written = row[2] or 0
    error_rate = errors / tool_calls if tool_calls > 0 else 0.0

    return {
        "sessions": sessions,
        "cost": cost,
        "loc_written": loc_written,
        "error_rate": error_rate,
        "user_turns": user_turns,
        "messages": messages,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
    }


async def get_sparkline_7d(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list:
    """Daily cost sparkline from daily_summaries.

    When no date range provided, shows last 7 days.
    """
    if not date_from and not date_to:
        end_date = date.today()
        start_date = end_date - timedelta(days=6)
        date_from = start_date.isoformat()
        date_to = end_date.isoformat()

    params: list = []
    filters = build_summary_filter(date_from, date_to, params)
    cursor = await db.execute(f"""
        SELECT date, cost
        FROM daily_summaries
        WHERE 1=1 {filters}
        ORDER BY date ASC
    """, params)
    rows = await cursor.fetchall()
    return [{"date": row[0], "value": row[1] or 0.0} for row in rows]


async def get_top_projects(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10
) -> list:
    """Top projects by cost. Two-query pattern."""
    params: list = []
    date_filter = build_date_filter("t.timestamp", date_from, date_to, params)

    # Query 1: Turn aggregates per project
    cursor = await db.execute(f"""
        SELECT
            s.project_path,
            s.project_display,
            COUNT(DISTINCT t.session_id) as sessions,
            SUM(t.cost) as cost,
            MAX(s.last_timestamp) as last_session
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE t.timestamp IS NOT NULL {date_filter}
        GROUP BY s.project_path
        ORDER BY cost DESC
        LIMIT ?
    """, params + [limit])
    rows = await cursor.fetchall()

    projects = {}
    for row in rows:
        projects[row[0]] = {
            "project_path": row[0],
            "project_display": row[1] or row[0],
            "sessions": row[2] or 0,
            "cost": row[3] or 0.0,
            "last_session": row[4],
            "loc_written": 0,
            "error_rate": 0.0,
        }

    if not projects:
        return []

    # Query 2: Tool call aggregates per project
    tc_params: list = []
    tc_date_filter = build_date_filter("tc.timestamp", date_from, date_to, tc_params)

    placeholders = ",".join("?" for _ in projects)
    tc_params.extend(projects.keys())

    cursor = await db.execute(f"""
        SELECT
            s.project_path,
            COUNT(*) as tool_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors,
            SUM(tc.loc_written) as loc_written
        FROM tool_calls tc
        JOIN sessions s ON tc.session_id = s.session_id
        WHERE tc.timestamp IS NOT NULL {tc_date_filter}
          AND s.project_path IN ({placeholders})
        GROUP BY s.project_path
    """, tc_params)
    rows = await cursor.fetchall()

    for row in rows:
        path = row[0]
        if path in projects:
            tool_calls = row[1] or 0
            errors = row[2] or 0
            projects[path]["loc_written"] = row[3] or 0
            projects[path]["error_rate"] = errors / tool_calls if tool_calls > 0 else 0.0

    return sorted(projects.values(), key=lambda p: p["cost"], reverse=True)


async def get_cost_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None
) -> list:
    """Daily cost trend from daily_summaries."""
    params: list = []
    filters = build_summary_filter(date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT date, cost, sessions, messages
        FROM daily_summaries
        WHERE 1=1 {filters}
        ORDER BY date ASC
    """, params)
    rows = await cursor.fetchall()
    return [
        {"date": row[0], "cost": row[1] or 0.0, "sessions": row[2] or 0, "messages": row[3] or 0}
        for row in rows
    ]


async def get_recent_sessions(
    db: aiosqlite.Connection,
    limit: int = 10,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> list:
    """Most recent sessions with key stats. Two-query pattern."""
    params: list = []
    date_filter = build_date_filter("s.first_timestamp", date_from, date_to, params)

    # Query 1: Session info + turns aggregates
    cursor = await db.execute(f"""
        SELECT
            s.session_id,
            s.project_display,
            s.first_timestamp,
            s.duration_seconds,
            s.is_agent,
            SUM(t.cost) as cost,
            COUNT(t.id) as turns,
            (SELECT t2.model FROM turns t2 WHERE t2.session_id = s.session_id
             AND t2.model IS NOT NULL AND t2.model NOT LIKE '<%'
             ORDER BY t2.timestamp DESC LIMIT 1) as model
        FROM sessions s
        LEFT JOIN turns t ON s.session_id = t.session_id
        WHERE s.first_timestamp IS NOT NULL {date_filter}
        GROUP BY s.session_id
        ORDER BY s.first_timestamp DESC
        LIMIT ?
    """, params + [limit])
    rows = await cursor.fetchall()

    return [
        {
            "session_id": row[0],
            "project_display": row[1],
            "first_timestamp": row[2],
            "duration_seconds": row[3] or 0,
            "is_agent": bool(row[4]),
            "cost": row[5] or 0.0,
            "turns": row[6] or 0,
            "model": row[7],
        }
        for row in rows
    ]


async def get_period_deltas(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Compare current period metrics to the equivalent previous period."""
    if not date_from or not date_to:
        return []

    from datetime import datetime, timedelta
    d_from = datetime.strptime(date_from, "%Y-%m-%d")
    d_to = datetime.strptime(date_to, "%Y-%m-%d")
    span = (d_to - d_from).days + 1
    prev_to = d_from - timedelta(days=1)
    prev_from = prev_to - timedelta(days=span - 1)

    async def _sum_period(start: str, end: str) -> Dict[str, float]:
        cursor = await db.execute("""
            SELECT
                COUNT(DISTINCT s.session_id) as sessions,
                COALESCE(SUM(t.cost), 0) as cost,
                COALESCE(SUM(t.input_tokens + t.output_tokens), 0) as tokens
            FROM turns t
            JOIN sessions s ON t.session_id = s.session_id
            WHERE t.timestamp IS NOT NULL
              AND date(t.timestamp, 'localtime') >= ? AND date(t.timestamp, 'localtime') <= ?
        """, (start, end))
        row = await cursor.fetchone()

        tc_cursor = await db.execute("""
            SELECT
                COALESCE(SUM(loc_written), 0) as loc_written,
                CASE WHEN COUNT(*) > 0
                    THEN CAST(SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) AS FLOAT) / COUNT(*)
                    ELSE 0 END as error_rate
            FROM tool_calls
            WHERE timestamp IS NOT NULL
              AND date(timestamp, 'localtime') >= ? AND date(timestamp, 'localtime') <= ?
        """, (start, end))
        tc_row = await tc_cursor.fetchone()

        return {
            "sessions": row[0] or 0,
            "cost": row[1] or 0,
            "tokens": row[2] or 0,
            "loc_written": tc_row[0] or 0,
            "error_rate": tc_row[1] or 0,
        }

    current = await _sum_period(date_from, date_to)
    previous = await _sum_period(prev_from.strftime("%Y-%m-%d"), prev_to.strftime("%Y-%m-%d"))

    deltas = []
    for metric in ["sessions", "cost", "loc_written", "error_rate"]:
        cur = current.get(metric, 0)
        prev = previous.get(metric, 0)
        delta = cur - prev
        pct = (delta / prev * 100) if prev != 0 else 0
        deltas.append({
            "metric": metric,
            "current": cur,
            "previous": prev,
            "delta": delta,
            "pct_change": round(pct, 1),
        })
    return deltas


async def get_activity_calendar(
    db: aiosqlite.Connection,
    days: int = 90,
) -> List[Dict[str, Any]]:
    """Daily activity counts for GitHub-style heatmap calendar."""
    cursor = await db.execute("""
        SELECT
            date,
            sessions,
            cost
        FROM daily_summaries
        WHERE date >= date('now', 'localtime', ?)
        ORDER BY date
    """, (f"-{days} days",))
    rows = await cursor.fetchall()
    return [{"date": r[0], "sessions": r[1] or 0, "cost": r[2] or 0} for r in rows]
