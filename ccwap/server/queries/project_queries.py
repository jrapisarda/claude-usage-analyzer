"""Project query module.

Uses the mandatory two-query pattern: separate turns and tool_calls queries
to avoid cross-product JOIN inflation.
"""

from typing import Optional, Tuple, List, Dict, Any

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter


# Valid sort columns for projects
VALID_SORT_COLUMNS = {
    "cost", "sessions", "messages", "loc_written", "error_rate",
    "input_tokens", "output_tokens", "user_turns", "duration_seconds",
    "cost_per_kloc", "tokens_per_loc", "project_display",
}


async def get_projects(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    sort: str = "cost",
    order: str = "desc",
    page: int = 1,
    limit: int = 50,
    search: Optional[str] = None,
) -> Tuple[List[Dict[str, Any]], int]:
    """
    Get paginated project list with full metrics.

    TWO-QUERY PATTERN:
    - Query 1: sessions + turns → token/cost aggregates per project
    - Query 2: tool_calls + sessions → LOC/error aggregates per project
    - Merge in Python, compute derived metrics

    Returns:
        Tuple of (projects list, total count)
    """
    # Build date filters
    turn_params: list = []
    turn_date_filter = build_date_filter("t.timestamp", date_from, date_to, turn_params)

    search_filter = ""
    if search:
        search_filter = " AND (s.project_path LIKE ? OR s.project_display LIKE ?)"
        search_pattern = f"%{search}%"
        turn_params.extend([search_pattern, search_pattern])

    # Query 1: Turns aggregates per project
    cursor = await db.execute(f"""
        SELECT
            s.project_path,
            s.project_display,
            COUNT(DISTINCT t.session_id) as sessions,
            COUNT(*) as messages,
            COUNT(CASE WHEN t.entry_type = 'user' THEN 1 END) as user_turns,
            SUM(t.input_tokens) as input_tokens,
            SUM(t.output_tokens) as output_tokens,
            SUM(t.cache_read_tokens) as cache_read_tokens,
            SUM(t.cache_write_tokens) as cache_write_tokens,
            SUM(t.thinking_chars) as thinking_chars,
            SUM(t.cost) as cost,
            SUM(s.duration_seconds) / COUNT(DISTINCT t.session_id) as avg_duration,
            COUNT(DISTINCT CASE WHEN s.is_agent = 1 THEN s.session_id END) as agent_sessions
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE t.timestamp IS NOT NULL {turn_date_filter} {search_filter}
        GROUP BY s.project_path
    """, turn_params)
    rows = await cursor.fetchall()

    projects: Dict[str, Dict[str, Any]] = {}
    for row in rows:
        path = row[0]
        projects[path] = {
            "project_path": path,
            "project_display": row[1] or path,
            "sessions": row[2] or 0,
            "messages": row[3] or 0,
            "user_turns": row[4] or 0,
            "input_tokens": row[5] or 0,
            "output_tokens": row[6] or 0,
            "cache_read_tokens": row[7] or 0,
            "cache_write_tokens": row[8] or 0,
            "thinking_chars": row[9] or 0,
            "cost": row[10] or 0.0,
            "duration_seconds": row[11] or 0,
            "agent_spawns": row[12] or 0,
            # Tool-call metrics (filled by query 2)
            "loc_written": 0,
            "loc_delivered": 0,
            "lines_added": 0,
            "lines_deleted": 0,
            "files_created": 0,
            "files_edited": 0,
            "error_count": 0,
            "error_rate": 0.0,
            "tool_calls": 0,
        }

    if not projects:
        return [], 0

    # Query 2: Tool call aggregates per project
    tc_params: list = []
    tc_date_filter = build_date_filter("tc.timestamp", date_from, date_to, tc_params)

    tc_search_filter = ""
    if search:
        tc_search_filter = " AND (s.project_path LIKE ? OR s.project_display LIKE ?)"
        tc_params.extend([search_pattern, search_pattern])

    cursor = await db.execute(f"""
        SELECT
            s.project_path,
            COUNT(*) as tool_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors,
            SUM(tc.loc_written) as loc_written,
            SUM(tc.lines_added) as lines_added,
            SUM(tc.lines_deleted) as lines_deleted,
            COUNT(DISTINCT CASE WHEN tc.tool_name = 'Write' THEN tc.file_path END) as files_created,
            COUNT(DISTINCT CASE WHEN tc.tool_name = 'Edit' THEN tc.file_path END) as files_edited
        FROM tool_calls tc
        JOIN sessions s ON tc.session_id = s.session_id
        WHERE tc.timestamp IS NOT NULL {tc_date_filter} {tc_search_filter}
        GROUP BY s.project_path
    """, tc_params)
    rows = await cursor.fetchall()

    for row in rows:
        path = row[0]
        if path in projects:
            tool_calls = row[1] or 0
            errors = row[2] or 0
            lines_added = row[4] or 0
            lines_deleted = row[5] or 0
            projects[path]["tool_calls"] = tool_calls
            projects[path]["error_count"] = errors
            projects[path]["error_rate"] = errors / tool_calls if tool_calls > 0 else 0.0
            projects[path]["loc_written"] = row[3] or 0
            projects[path]["lines_added"] = lines_added
            projects[path]["lines_deleted"] = lines_deleted
            projects[path]["loc_delivered"] = lines_added - lines_deleted
            projects[path]["files_created"] = row[6] or 0
            projects[path]["files_edited"] = row[7] or 0

    # Compute derived metrics
    for p in projects.values():
        loc = p["loc_written"]
        if loc > 0:
            p["cost_per_kloc"] = p["cost"] / (loc / 1000)
            p["tokens_per_loc"] = p["output_tokens"] / loc
        else:
            p["cost_per_kloc"] = 0.0
            p["tokens_per_loc"] = 0.0

        total_input = p["input_tokens"] + p["cache_read_tokens"]
        p["cache_hit_rate"] = p["cache_read_tokens"] / total_input if total_input > 0 else 0.0

        if p["user_turns"] > 0:
            p["avg_turn_cost"] = p["cost"] / p["user_turns"]
        else:
            p["avg_turn_cost"] = 0.0

    # Sort
    sort_key = sort if sort in VALID_SORT_COLUMNS else "cost"
    project_list = sorted(
        projects.values(),
        key=lambda p: p.get(sort_key, 0) or 0,
        reverse=(order == "desc"),
    )

    total_count = len(project_list)

    # Paginate
    offset = (page - 1) * limit
    paginated = project_list[offset:offset + limit]

    return paginated, total_count
