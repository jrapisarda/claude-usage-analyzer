"""Productivity query module."""

from typing import Optional, Dict, Any, List

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter, build_summary_filter


async def get_efficiency_summary(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Efficiency summary cards. Two-query pattern."""
    params: list = []
    filters = build_summary_filter(date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            SUM(loc_written), SUM(loc_delivered), SUM(sessions),
            SUM(cost), SUM(tool_calls), SUM(errors),
            SUM(output_tokens)
        FROM daily_summaries
        WHERE 1=1 {filters}
    """, params)
    row = await cursor.fetchone()

    loc_written = row[0] or 0
    loc_delivered = row[1] or 0
    sessions = row[2] or 0
    cost = row[3] or 0.0
    tool_calls = row[4] or 0
    errors = row[5] or 0
    output_tokens = row[6] or 0

    return {
        "total_loc_written": loc_written,
        "total_loc_delivered": loc_delivered,
        "avg_loc_per_session": loc_written / sessions if sessions > 0 else 0,
        "cost_per_kloc": cost / (loc_written / 1000) if loc_written > 0 else 0,
        "tokens_per_loc": output_tokens / loc_written if loc_written > 0 else 0,
        "error_rate": errors / tool_calls if tool_calls > 0 else 0,
    }


async def get_loc_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """LOC trend from daily_summaries."""
    params: list = []
    filters = build_summary_filter(date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT date, loc_written, loc_delivered, lines_added, lines_deleted
        FROM daily_summaries
        WHERE 1=1 {filters}
        ORDER BY date ASC
    """, params)
    rows = await cursor.fetchall()

    return [
        {
            "date": row[0],
            "loc_written": row[1] or 0,
            "loc_delivered": row[2] or 0,
            "lines_added": row[3] or 0,
            "lines_deleted": row[4] or 0,
        }
        for row in rows
    ]


async def get_language_breakdown(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """LOC by programming language."""
    params: list = []
    filters = build_date_filter("tc.timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            COALESCE(tc.language, 'unknown') as language,
            SUM(tc.loc_written) as loc_written,
            COUNT(DISTINCT tc.file_path) as files_count
        FROM tool_calls tc
        WHERE tc.language IS NOT NULL {filters}
        GROUP BY tc.language
        ORDER BY loc_written DESC
    """, params)
    rows = await cursor.fetchall()

    total_loc = sum(r[1] or 0 for r in rows)
    return [
        {
            "language": row[0],
            "loc_written": row[1] or 0,
            "files_count": row[2] or 0,
            "percentage": ((row[1] or 0) / total_loc * 100) if total_loc > 0 else 0,
        }
        for row in rows
    ]


async def get_tool_usage(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Tool usage statistics."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            tool_name,
            COUNT(*) as total_calls,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as error_count,
            SUM(loc_written) as loc_written
        FROM tool_calls
        WHERE 1=1 {filters}
        GROUP BY tool_name
        ORDER BY total_calls DESC
    """, params)
    rows = await cursor.fetchall()

    return [
        {
            "tool_name": row[0],
            "total_calls": row[1] or 0,
            "success_count": row[2] or 0,
            "error_count": row[3] or 0,
            "success_rate": (row[2] or 0) / row[1] if row[1] else 0,
            "loc_written": row[4] or 0,
        }
        for row in rows
    ]


async def get_error_analysis(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Error analysis with categories."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    # Total errors and tool calls
    cursor = await db.execute(f"""
        SELECT
            COUNT(*) as total_calls,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as total_errors
        FROM tool_calls
        WHERE 1=1 {filters}
    """, params)
    row = await cursor.fetchone()
    total_calls = row[0] or 0
    total_errors = row[1] or 0
    error_rate = total_errors / total_calls if total_calls > 0 else 0

    # By category
    cursor = await db.execute(f"""
        SELECT
            COALESCE(error_category, 'Other') as category,
            COUNT(*) as count
        FROM tool_calls
        WHERE success = 0 {filters}
        GROUP BY error_category
        ORDER BY count DESC
    """, params)
    cat_rows = await cursor.fetchall()

    categories = [
        {
            "category": row[0],
            "count": row[1] or 0,
            "percentage": ((row[1] or 0) / total_errors * 100) if total_errors > 0 else 0,
        }
        for row in cat_rows
    ]

    return {
        "total_errors": total_errors,
        "error_rate": error_rate,
        "categories": categories,
        "top_errors": [],
    }


async def get_efficiency_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daily cost per kLOC.
    Returns: date, cost_per_kloc."""
    params: list = []
    filters = build_summary_filter(date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT date, cost, loc_written
        FROM daily_summaries
        WHERE 1=1 {filters}
        ORDER BY date ASC
    """, params)
    rows = await cursor.fetchall()

    return [
        {
            "date": row[0],
            "cost_per_kloc": (row[1] or 0) / ((row[2] or 0) / 1000) if (row[2] or 0) > 0 else 0.0,
        }
        for row in rows
    ]


async def get_language_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daily LOC by language.
    Returns: date, language, loc_written."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            date(timestamp, 'localtime') as day,
            COALESCE(language, 'unknown') as language,
            SUM(loc_written) as loc_written
        FROM tool_calls
        WHERE language IS NOT NULL AND timestamp IS NOT NULL {filters}
        GROUP BY day, language
        ORDER BY day ASC, loc_written DESC
    """, params)
    rows = await cursor.fetchall()

    return [
        {
            "date": row[0],
            "language": row[1],
            "loc_written": row[2] or 0,
        }
        for row in rows
    ]


async def get_tool_success_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daily success rate per tool.
    Returns: date, tool_name, success_rate, total."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            date(timestamp, 'localtime') as day,
            tool_name,
            COUNT(*) as total,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as success_count
        FROM tool_calls
        WHERE timestamp IS NOT NULL {filters}
        GROUP BY day, tool_name
        ORDER BY day ASC, total DESC
    """, params)
    rows = await cursor.fetchall()

    return [
        {
            "date": row[0],
            "tool_name": row[1],
            "success_rate": (row[3] or 0) / row[2] if row[2] else 0.0,
            "total": row[2] or 0,
        }
        for row in rows
    ]


async def get_file_churn(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
) -> List[Dict[str, Any]]:
    """Top files by edit count.
    Returns: file_path, edit_count, total_loc."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            file_path,
            COUNT(*) as edit_count,
            SUM(loc_written) as total_loc
        FROM tool_calls
        WHERE file_path IS NOT NULL {filters}
        GROUP BY file_path
        ORDER BY edit_count DESC
        LIMIT ?
    """, params + [limit])
    rows = await cursor.fetchall()

    return [
        {
            "file_path": row[0],
            "edit_count": row[1] or 0,
            "total_loc": row[2] or 0,
        }
        for row in rows
    ]


async def get_file_hotspots(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 20,
) -> List[Dict[str, Any]]:
    """Most-touched files."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            file_path,
            SUM(CASE WHEN tool_name = 'Edit' THEN 1 ELSE 0 END) as edit_count,
            SUM(CASE WHEN tool_name = 'Write' THEN 1 ELSE 0 END) as write_count,
            COUNT(*) as total_touches,
            SUM(loc_written) as loc_written,
            MAX(language) as language
        FROM tool_calls
        WHERE file_path IS NOT NULL {filters}
        GROUP BY file_path
        ORDER BY total_touches DESC
        LIMIT ?
    """, params + [limit])
    rows = await cursor.fetchall()

    return [
        {
            "file_path": row[0],
            "edit_count": row[1] or 0,
            "write_count": row[2] or 0,
            "total_touches": row[3] or 0,
            "loc_written": row[4] or 0,
            "language": row[5],
        }
        for row in rows
    ]
