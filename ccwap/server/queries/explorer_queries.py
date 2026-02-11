"""Analytics explorer query module.

Builds dynamic SQL queries based on metric type, grouping dimensions,
and optional filters. Dispatches to the correct table(s) to avoid
cross-product JOINs.
"""

from typing import Optional, List, Dict, Any, Tuple

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter, build_summary_filter


# Dimension column expressions per table context
_TURNS_DIM_COLS = {
    "date": "date(t.timestamp, 'localtime')",
    "model": "t.model",
    "project": "COALESCE(s.project_display, s.project_path)",
    "branch": "COALESCE(s.git_branch, 'unknown')",
    "cc_version": "COALESCE(s.cc_version, 'unknown')",
    "entry_type": "COALESCE(t.entry_type, 'unknown')",
    "is_agent": "CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END",
}

_TOOL_DIM_COLS = {
    "date": "date(tc.timestamp, 'localtime')",
    "model": "t.model",
    "project": "COALESCE(s.project_display, s.project_path)",
    "branch": "COALESCE(s.git_branch, 'unknown')",
    "language": "COALESCE(tc.language, 'unknown')",
    "tool_name": "COALESCE(tc.tool_name, 'unknown')",
    "cc_version": "COALESCE(s.cc_version, 'unknown')",
    "entry_type": "COALESCE(t.entry_type, 'unknown')",
    "is_agent": "CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END",
}

_SESSION_DIM_COLS = {
    "date": "date(s.first_timestamp, 'localtime')",
    "project": "COALESCE(s.project_display, s.project_path)",
    "branch": "COALESCE(s.git_branch, 'unknown')",
    "cc_version": "COALESCE(s.cc_version, 'unknown')",
    "is_agent": "CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END",
}

# Dimension columns for optional materialized aggregates
_TURNS_MAT_DIM_COLS = {
    "date": "a.date",
    "model": "a.model",
    "project": "a.project",
    "branch": "a.branch",
    "cc_version": "a.cc_version",
    "entry_type": "a.entry_type",
    "is_agent": "a.is_agent",
}

_TOOL_MAT_DIM_COLS = {
    "date": "a.date",
    "model": "a.model",
    "project": "a.project",
    "branch": "a.branch",
    "language": "a.language",
    "tool_name": "a.tool_name",
    "cc_version": "a.cc_version",
    "entry_type": "a.entry_type",
    "is_agent": "a.is_agent",
}

_SESSION_MAT_DIM_COLS = {
    "date": "a.date",
    "project": "a.project",
    "branch": "a.branch",
    "cc_version": "a.cc_version",
    "is_agent": "a.is_agent",
}

# Metric aggregation expressions
_TURNS_AGG = {
    "cost": "SUM(t.cost)",
    "input_tokens": "SUM(t.input_tokens)",
    "output_tokens": "SUM(t.output_tokens)",
    "cache_read_tokens": "SUM(t.cache_read_tokens)",
    "cache_write_tokens": "SUM(t.cache_write_tokens)",
    "ephemeral_5m_tokens": "SUM(t.ephemeral_5m_tokens)",
    "ephemeral_1h_tokens": "SUM(t.ephemeral_1h_tokens)",
    "thinking_chars": "SUM(t.thinking_chars)",
    "turns_count": "COUNT(*)",
}

_TOOL_AGG = {
    "loc_written": "SUM(tc.loc_written)",
    "tool_calls_count": "COUNT(*)",
    "errors": "SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END)",
    "lines_added": "SUM(tc.lines_added)",
    "lines_deleted": "SUM(tc.lines_deleted)",
}

_SESSION_AGG = {
    "sessions_count": "COUNT(*)",
    "duration_seconds": "SUM(s.duration_seconds)",
}

# Aggregation columns in materialized aggregate tables
_TURNS_MAT_AGG = {
    "cost": "cost",
    "input_tokens": "input_tokens",
    "output_tokens": "output_tokens",
    "cache_read_tokens": "cache_read_tokens",
    "cache_write_tokens": "cache_write_tokens",
    "ephemeral_5m_tokens": "ephemeral_5m_tokens",
    "ephemeral_1h_tokens": "ephemeral_1h_tokens",
    "thinking_chars": "thinking_chars",
    "turns_count": "turns_count",
}

_TOOL_MAT_AGG = {
    "loc_written": "loc_written",
    "tool_calls_count": "tool_calls_count",
    "errors": "errors",
    "lines_added": "lines_added",
    "lines_deleted": "lines_deleted",
}

_SESSION_MAT_AGG = {
    "sessions_count": "sessions_count",
    "duration_seconds": "duration_seconds",
}

# Which metrics belong to which table context
_TURNS_METRICS = set(_TURNS_AGG.keys())
_TOOL_METRICS = set(_TOOL_AGG.keys())
_SESSION_METRICS = set(_SESSION_AGG.keys())


def _build_date_filter(
    timestamp_col: str,
    date_from: Optional[str],
    date_to: Optional[str],
    params: list,
) -> str:
    """Build date filter clause with localtime conversion."""
    return build_date_filter(timestamp_col, date_from, date_to, params)


def _build_summary_date_filter(
    date_from: Optional[str],
    date_to: Optional[str],
    params: list,
) -> str:
    """Build date filter clause for summary tables with local-date column."""
    return build_summary_filter(date_from, date_to, params)


async def _materialized_table_ready(db: aiosqlite.Connection, table_name: str) -> bool:
    """Check whether a materialized table exists and has at least one row."""
    try:
        cursor = await db.execute(f"SELECT 1 FROM {table_name} LIMIT 1")  # noqa: S608
        return (await cursor.fetchone()) is not None
    except Exception:
        return False


def _build_model_exclusion(
    model_col: str,
    group_by: str,
    split_by: Optional[str],
) -> str:
    """Exclude NULL and synthetic models when model is a dimension."""
    if group_by == "model" or split_by == "model":
        return f" AND {model_col} IS NOT NULL AND {model_col} NOT LIKE '<%'"
    return ""


def _build_list_filter(
    col_expr: str,
    values: Optional[List[str]],
    params: list,
) -> str:
    """Build IN (...) filter clause for a list of values."""
    if not values:
        return ""
    placeholders = ", ".join("?" for _ in values)
    params.extend(values)
    return f" AND {col_expr} IN ({placeholders})"


def _build_bucket_filter(
    col_expr: str,
    value: str,
    params: list,
) -> str:
    """Build equality filter for a selected group/split bucket value."""
    params.append(value)
    return f" AND {col_expr} = ?"


async def _query_turns_metric(
    db: aiosqlite.Connection,
    metric: str,
    group_by: str,
    split_by: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    projects: Optional[List[str]],
    models: Optional[List[str]],
    branches: Optional[List[str]],
    languages: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Query turns-based metrics (cost, tokens, etc.)."""
    params: list = []
    agg = _TURNS_AGG[metric]

    group_col = _TURNS_DIM_COLS[group_by]
    select_cols = f"{group_col} AS grp"
    group_clause = "grp"

    if split_by:
        split_col = _TURNS_DIM_COLS[split_by]
        select_cols += f", {split_col} AS spl"
        group_clause += ", spl"

    filters = ""
    filters += _build_model_exclusion("t.model", group_by, split_by)
    filters += _build_date_filter("t.timestamp", date_from, date_to, params)
    filters += _build_list_filter(
        "COALESCE(s.project_display, s.project_path)", projects, params
    )
    filters += _build_list_filter("t.model", models, params)
    filters += _build_list_filter("s.git_branch", branches, params)
    # languages not applicable for turns

    sql = f"""
        SELECT {select_cols}, {agg} AS val
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE 1=1 {filters}
        GROUP BY {group_clause}
        ORDER BY grp
    """

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()

    result = []
    for r in rows:
        row_dict = {"group": str(r[0]), "value": float(r[-1] or 0)}
        if split_by:
            row_dict["split"] = str(r[1])
        result.append(row_dict)
    return result


async def _query_tool_metric(
    db: aiosqlite.Connection,
    metric: str,
    group_by: str,
    split_by: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    projects: Optional[List[str]],
    models: Optional[List[str]],
    branches: Optional[List[str]],
    languages: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Query tool_calls-based metrics (LOC, tool count, errors)."""
    params: list = []
    agg = _TOOL_AGG[metric]

    # Determine if we need turns join (for model, entry_type dimensions)
    needs_turns = group_by in ("model", "entry_type") or split_by in ("model", "entry_type")

    group_col = _TOOL_DIM_COLS[group_by]
    select_cols = f"{group_col} AS grp"
    group_clause = "grp"

    if split_by:
        split_col = _TOOL_DIM_COLS[split_by]
        select_cols += f", {split_col} AS spl"
        group_clause += ", spl"

    joins = "FROM tool_calls tc JOIN sessions s ON tc.session_id = s.session_id"
    if needs_turns:
        joins += " JOIN turns t ON tc.turn_id = t.id"

    filters = ""
    if needs_turns:
        filters += _build_model_exclusion("t.model", group_by, split_by)
    filters += _build_date_filter("tc.timestamp", date_from, date_to, params)
    filters += _build_list_filter(
        "COALESCE(s.project_display, s.project_path)", projects, params
    )
    if needs_turns:
        filters += _build_list_filter("t.model", models, params)
    filters += _build_list_filter("s.git_branch", branches, params)
    filters += _build_list_filter("tc.language", languages, params)

    sql = f"""
        SELECT {select_cols}, {agg} AS val
        {joins}
        WHERE 1=1 {filters}
        GROUP BY {group_clause}
        ORDER BY grp
    """

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()

    result = []
    for r in rows:
        row_dict = {"group": str(r[0]), "value": float(r[-1] or 0)}
        if split_by:
            row_dict["split"] = str(r[1])
        result.append(row_dict)
    return result


async def _query_session_metric(
    db: aiosqlite.Connection,
    metric: str,
    group_by: str,
    split_by: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    projects: Optional[List[str]],
    models: Optional[List[str]],
    branches: Optional[List[str]],
    languages: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Query session-based metrics (session count, duration)."""
    params: list = []
    agg = _SESSION_AGG[metric]

    group_col = _SESSION_DIM_COLS[group_by]
    select_cols = f"{group_col} AS grp"
    group_clause = "grp"

    if split_by:
        split_col = _SESSION_DIM_COLS[split_by]
        select_cols += f", {split_col} AS spl"
        group_clause += ", spl"

    filters = ""
    filters += _build_date_filter("s.first_timestamp", date_from, date_to, params)
    filters += _build_list_filter(
        "COALESCE(s.project_display, s.project_path)", projects, params
    )
    filters += _build_list_filter("s.git_branch", branches, params)
    # models and languages not applicable for sessions

    sql = f"""
        SELECT {select_cols}, {agg} AS val
        FROM sessions s
        WHERE 1=1 {filters}
        GROUP BY {group_clause}
        ORDER BY grp
    """

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()

    result = []
    for r in rows:
        row_dict = {"group": str(r[0]), "value": float(r[-1] or 0)}
        if split_by:
            row_dict["split"] = str(r[1])
        result.append(row_dict)
    return result


async def _query_turns_metric_materialized(
    db: aiosqlite.Connection,
    metric: str,
    group_by: str,
    split_by: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    projects: Optional[List[str]],
    models: Optional[List[str]],
    branches: Optional[List[str]],
    languages: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Query turns metrics from materialized summary table."""
    params: list = []
    metric_col = _TURNS_MAT_AGG[metric]

    group_col = _TURNS_MAT_DIM_COLS[group_by]
    select_cols = f"{group_col} AS grp"
    group_clause = "grp"
    if split_by:
        split_col = _TURNS_MAT_DIM_COLS[split_by]
        select_cols += f", {split_col} AS spl"
        group_clause += ", spl"

    filters = ""
    if group_by == "model" or split_by == "model":
        filters += " AND a.model != 'unknown' AND a.model NOT LIKE '<%'"
    filters += _build_summary_date_filter(date_from, date_to, params)
    filters += _build_list_filter("a.project", projects, params)
    filters += _build_list_filter("a.model", models, params)
    filters += _build_list_filter("a.branch", branches, params)

    sql = f"""
        SELECT {select_cols}, SUM(a.{metric_col}) AS val
        FROM turns_agg_daily a
        WHERE 1=1 {filters}
        GROUP BY {group_clause}
        ORDER BY grp
    """

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()

    result = []
    for r in rows:
        row_dict = {"group": str(r[0]), "value": float(r[-1] or 0)}
        if split_by:
            row_dict["split"] = str(r[1])
        result.append(row_dict)
    return result


async def _query_tool_metric_materialized(
    db: aiosqlite.Connection,
    metric: str,
    group_by: str,
    split_by: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    projects: Optional[List[str]],
    models: Optional[List[str]],
    branches: Optional[List[str]],
    languages: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Query tool metrics from materialized summary table."""
    params: list = []
    metric_col = _TOOL_MAT_AGG[metric]

    group_col = _TOOL_MAT_DIM_COLS[group_by]
    select_cols = f"{group_col} AS grp"
    group_clause = "grp"
    if split_by:
        split_col = _TOOL_MAT_DIM_COLS[split_by]
        select_cols += f", {split_col} AS spl"
        group_clause += ", spl"

    # Keep behavior aligned with raw query path.
    needs_turns = group_by in ("model", "entry_type") or split_by in ("model", "entry_type")

    filters = ""
    if group_by == "model" or split_by == "model":
        filters += " AND a.model != 'unknown' AND a.model NOT LIKE '<%'"
    filters += _build_summary_date_filter(date_from, date_to, params)
    filters += _build_list_filter("a.project", projects, params)
    if needs_turns:
        filters += _build_list_filter("a.model", models, params)
    filters += _build_list_filter("a.branch", branches, params)
    filters += _build_list_filter("a.language", languages, params)

    sql = f"""
        SELECT {select_cols}, SUM(a.{metric_col}) AS val
        FROM tool_calls_agg_daily a
        WHERE 1=1 {filters}
        GROUP BY {group_clause}
        ORDER BY grp
    """

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()

    result = []
    for r in rows:
        row_dict = {"group": str(r[0]), "value": float(r[-1] or 0)}
        if split_by:
            row_dict["split"] = str(r[1])
        result.append(row_dict)
    return result


async def _query_session_metric_materialized(
    db: aiosqlite.Connection,
    metric: str,
    group_by: str,
    split_by: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    projects: Optional[List[str]],
    models: Optional[List[str]],
    branches: Optional[List[str]],
    languages: Optional[List[str]],
) -> List[Dict[str, Any]]:
    """Query session metrics from materialized summary table."""
    params: list = []
    metric_col = _SESSION_MAT_AGG[metric]

    group_col = _SESSION_MAT_DIM_COLS[group_by]
    select_cols = f"{group_col} AS grp"
    group_clause = "grp"
    if split_by:
        split_col = _SESSION_MAT_DIM_COLS[split_by]
        select_cols += f", {split_col} AS spl"
        group_clause += ", spl"

    filters = ""
    filters += _build_summary_date_filter(date_from, date_to, params)
    filters += _build_list_filter("a.project", projects, params)
    filters += _build_list_filter("a.branch", branches, params)

    sql = f"""
        SELECT {select_cols}, SUM(a.{metric_col}) AS val
        FROM sessions_agg_daily a
        WHERE 1=1 {filters}
        GROUP BY {group_clause}
        ORDER BY grp
    """

    cursor = await db.execute(sql, params)
    rows = await cursor.fetchall()

    result = []
    for r in rows:
        row_dict = {"group": str(r[0]), "value": float(r[-1] or 0)}
        if split_by:
            row_dict["split"] = str(r[1])
        result.append(row_dict)
    return result


async def query_explorer(
    db: aiosqlite.Connection,
    metric: str,
    group_by: str,
    split_by: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    projects: Optional[List[str]] = None,
    models: Optional[List[str]] = None,
    branches: Optional[List[str]] = None,
    languages: Optional[List[str]] = None,
    use_materialized: bool = False,
) -> Tuple[List[Dict[str, Any]], Dict[str, Any]]:
    """
    Execute explorer query and return (rows, metadata).

    Dispatches to the correct query function based on metric type.
    """
    if use_materialized and metric in _TURNS_METRICS:
        if await _materialized_table_ready(db, "turns_agg_daily"):
            rows = await _query_turns_metric_materialized(
                db, metric, group_by, split_by,
                date_from, date_to, projects, models, branches, languages,
            )
        else:
            rows = await _query_turns_metric(
                db, metric, group_by, split_by,
                date_from, date_to, projects, models, branches, languages,
            )
    elif use_materialized and metric in _TOOL_METRICS:
        if await _materialized_table_ready(db, "tool_calls_agg_daily"):
            rows = await _query_tool_metric_materialized(
                db, metric, group_by, split_by,
                date_from, date_to, projects, models, branches, languages,
            )
        else:
            rows = await _query_tool_metric(
                db, metric, group_by, split_by,
                date_from, date_to, projects, models, branches, languages,
            )
    elif use_materialized and metric in _SESSION_METRICS:
        if await _materialized_table_ready(db, "sessions_agg_daily"):
            rows = await _query_session_metric_materialized(
                db, metric, group_by, split_by,
                date_from, date_to, projects, models, branches, languages,
            )
        else:
            rows = await _query_session_metric(
                db, metric, group_by, split_by,
                date_from, date_to, projects, models, branches, languages,
            )
    elif metric in _TURNS_METRICS:
        rows = await _query_turns_metric(
            db, metric, group_by, split_by,
            date_from, date_to, projects, models, branches, languages,
        )
    elif metric in _TOOL_METRICS:
        rows = await _query_tool_metric(
            db, metric, group_by, split_by,
            date_from, date_to, projects, models, branches, languages,
        )
    elif metric in _SESSION_METRICS:
        rows = await _query_session_metric(
            db, metric, group_by, split_by,
            date_from, date_to, projects, models, branches, languages,
        )
    else:
        rows = []

    # Build metadata
    total = sum(r["value"] for r in rows)
    groups = sorted(set(r["group"] for r in rows))
    splits = sorted(set(r.get("split", "") for r in rows if r.get("split")))

    metadata = {
        "metric": metric,
        "group_by": group_by,
        "split_by": split_by,
        "total": total,
        "row_count": len(rows),
        "groups": groups,
        "splits": splits,
    }

    return rows, metadata


def _build_turns_drilldown_cte(
    metric: str,
    group_by: str,
    group_value: str,
    split_by: Optional[str],
    split_value: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    projects: Optional[List[str]],
    models: Optional[List[str]],
    branches: Optional[List[str]],
) -> Tuple[str, list]:
    """Build candidate session CTE for turns-based metrics."""
    params: list = []
    agg = _TURNS_AGG[metric]

    filters = ""
    filters += _build_model_exclusion("t.model", group_by, split_by)
    filters += _build_date_filter("t.timestamp", date_from, date_to, params)
    filters += _build_list_filter(
        "COALESCE(s.project_display, s.project_path)", projects, params
    )
    filters += _build_list_filter("t.model", models, params)
    filters += _build_list_filter("s.git_branch", branches, params)
    filters += _build_bucket_filter(_TURNS_DIM_COLS[group_by], group_value, params)
    if split_by and split_value is not None:
        filters += _build_bucket_filter(_TURNS_DIM_COLS[split_by], split_value, params)

    cte = f"""
        candidate_sessions AS (
            SELECT
                s.session_id,
                {agg} AS bucket_value
            FROM turns t
            JOIN sessions s ON t.session_id = s.session_id
            WHERE 1=1 {filters}
            GROUP BY s.session_id
        )
    """
    return cte, params


def _build_tool_drilldown_cte(
    metric: str,
    group_by: str,
    group_value: str,
    split_by: Optional[str],
    split_value: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    projects: Optional[List[str]],
    models: Optional[List[str]],
    branches: Optional[List[str]],
    languages: Optional[List[str]],
) -> Tuple[str, list]:
    """Build candidate session CTE for tool-call-based metrics."""
    params: list = []
    agg = _TOOL_AGG[metric]

    needs_turns = (
        group_by in ("model", "entry_type")
        or split_by in ("model", "entry_type")
        or bool(models)
    )

    joins = "FROM tool_calls tc JOIN sessions s ON tc.session_id = s.session_id"
    if needs_turns:
        joins += " JOIN turns t ON tc.turn_id = t.id"

    filters = ""
    if needs_turns:
        filters += _build_model_exclusion("t.model", group_by, split_by)
    filters += _build_date_filter("tc.timestamp", date_from, date_to, params)
    filters += _build_list_filter(
        "COALESCE(s.project_display, s.project_path)", projects, params
    )
    if needs_turns:
        filters += _build_list_filter("t.model", models, params)
    filters += _build_list_filter("s.git_branch", branches, params)
    filters += _build_list_filter("tc.language", languages, params)
    filters += _build_bucket_filter(_TOOL_DIM_COLS[group_by], group_value, params)
    if split_by and split_value is not None:
        filters += _build_bucket_filter(_TOOL_DIM_COLS[split_by], split_value, params)

    cte = f"""
        candidate_sessions AS (
            SELECT
                s.session_id,
                {agg} AS bucket_value
            {joins}
            WHERE 1=1 {filters}
            GROUP BY s.session_id
        )
    """
    return cte, params


def _build_session_drilldown_cte(
    metric: str,
    group_by: str,
    group_value: str,
    split_by: Optional[str],
    split_value: Optional[str],
    date_from: Optional[str],
    date_to: Optional[str],
    projects: Optional[List[str]],
    branches: Optional[List[str]],
) -> Tuple[str, list]:
    """Build candidate session CTE for session-based metrics."""
    params: list = []
    agg = _SESSION_AGG[metric]

    filters = ""
    filters += _build_date_filter("s.first_timestamp", date_from, date_to, params)
    filters += _build_list_filter(
        "COALESCE(s.project_display, s.project_path)", projects, params
    )
    filters += _build_list_filter("s.git_branch", branches, params)
    filters += _build_bucket_filter(_SESSION_DIM_COLS[group_by], group_value, params)
    if split_by and split_value is not None:
        filters += _build_bucket_filter(_SESSION_DIM_COLS[split_by], split_value, params)

    cte = f"""
        candidate_sessions AS (
            SELECT
                s.session_id,
                {agg} AS bucket_value
            FROM sessions s
            WHERE 1=1 {filters}
            GROUP BY s.session_id
        )
    """
    return cte, params


async def query_explorer_drilldown(
    db: aiosqlite.Connection,
    metric: str,
    group_by: str,
    group_value: str,
    split_by: Optional[str] = None,
    split_value: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    projects: Optional[List[str]] = None,
    models: Optional[List[str]] = None,
    branches: Optional[List[str]] = None,
    languages: Optional[List[str]] = None,
    page: int = 1,
    limit: int = 25,
) -> Tuple[List[Dict[str, Any]], int]:
    """Return paginated sessions that contribute to a selected explorer bucket."""
    if metric in _TURNS_METRICS:
        candidate_cte, params = _build_turns_drilldown_cte(
            metric=metric,
            group_by=group_by,
            group_value=group_value,
            split_by=split_by,
            split_value=split_value,
            date_from=date_from,
            date_to=date_to,
            projects=projects,
            models=models,
            branches=branches,
        )
    elif metric in _TOOL_METRICS:
        candidate_cte, params = _build_tool_drilldown_cte(
            metric=metric,
            group_by=group_by,
            group_value=group_value,
            split_by=split_by,
            split_value=split_value,
            date_from=date_from,
            date_to=date_to,
            projects=projects,
            models=models,
            branches=branches,
            languages=languages,
        )
    elif metric in _SESSION_METRICS:
        candidate_cte, params = _build_session_drilldown_cte(
            metric=metric,
            group_by=group_by,
            group_value=group_value,
            split_by=split_by,
            split_value=split_value,
            date_from=date_from,
            date_to=date_to,
            projects=projects,
            branches=branches,
        )
    else:
        return [], 0

    count_cursor = await db.execute(
        f"WITH {candidate_cte} SELECT COUNT(*) FROM candidate_sessions",
        params,
    )
    count_row = await count_cursor.fetchone()
    total_count = int(count_row[0] or 0)
    if total_count == 0:
        return [], 0

    offset = (page - 1) * limit
    query_params = list(params) + [limit, offset]
    cursor = await db.execute(f"""
        WITH {candidate_cte}
        SELECT
            s.session_id,
            COALESCE(s.project_display, s.project_path) AS project,
            s.first_timestamp,
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END AS user_type,
            COALESCE(s.git_branch, 'unknown') AS branch,
            COALESCE(s.cc_version, 'unknown') AS cc_version,
            cs.bucket_value,
            COALESCE(turn_agg.total_cost, 0) AS total_cost,
            COALESCE(turn_agg.turns, 0) AS turns,
            COALESCE(tc_agg.tool_calls, 0) AS tool_calls,
            COALESCE(tc_agg.errors, 0) AS errors
        FROM candidate_sessions cs
        JOIN sessions s ON s.session_id = cs.session_id
        LEFT JOIN (
            SELECT
                t.session_id,
                SUM(t.cost) AS total_cost,
                COUNT(*) AS turns
            FROM turns t
            GROUP BY t.session_id
        ) turn_agg ON turn_agg.session_id = s.session_id
        LEFT JOIN (
            SELECT
                tc.session_id,
                COUNT(*) AS tool_calls,
                SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) AS errors
            FROM tool_calls tc
            GROUP BY tc.session_id
        ) tc_agg ON tc_agg.session_id = s.session_id
        ORDER BY cs.bucket_value DESC, total_cost DESC, s.first_timestamp DESC
        LIMIT ? OFFSET ?
    """, query_params)
    rows = await cursor.fetchall()

    sessions = [{
        "session_id": r[0],
        "project": str(r[1]),
        "first_timestamp": r[2],
        "user_type": r[3],
        "branch": str(r[4]),
        "cc_version": str(r[5]),
        "bucket_value": float(r[6] or 0),
        "total_cost": float(r[7] or 0),
        "turns": int(r[8] or 0),
        "tool_calls": int(r[9] or 0),
        "errors": int(r[10] or 0),
    } for r in rows]

    return sessions, total_count


async def get_filter_options(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Get available filter options for dropdowns."""
    turns_params: list = []
    date_filter_turns = build_date_filter("t.timestamp", date_from, date_to, turns_params)
    session_params: list = []
    date_filter_sessions = build_date_filter("s.first_timestamp", date_from, date_to, session_params)
    tool_params: list = []
    date_filter_tools = build_date_filter("tc.timestamp", date_from, date_to, tool_params)

    # Projects (from sessions)
    p_params = list(session_params)
    cursor = await db.execute(f"""
        SELECT COALESCE(s.project_display, s.project_path) AS proj,
               COUNT(DISTINCT s.session_id) AS cnt
        FROM sessions s
        WHERE 1=1 {date_filter_sessions}
        GROUP BY proj
        ORDER BY cnt DESC
        LIMIT 100
    """, p_params)
    project_rows = await cursor.fetchall()
    projects = [
        {"value": str(r[0]), "label": str(r[0]), "count": r[1]}
        for r in project_rows
    ]

    # Models (from turns) — exclude NULL and synthetic
    m_params = list(turns_params)
    cursor = await db.execute(f"""
        SELECT t.model AS mdl,
               COUNT(*) AS cnt
        FROM turns t
        WHERE t.model IS NOT NULL AND t.model NOT LIKE '<%' {date_filter_turns}
        GROUP BY mdl
        ORDER BY cnt DESC
        LIMIT 50
    """, m_params)
    model_rows = await cursor.fetchall()
    models_list = [
        {"value": str(r[0]), "label": str(r[0]), "count": r[1]}
        for r in model_rows
    ]

    # Branches (from sessions)
    b_params = list(session_params)
    cursor = await db.execute(f"""
        SELECT COALESCE(s.git_branch, 'unknown') AS br,
               COUNT(DISTINCT s.session_id) AS cnt
        FROM sessions s
        WHERE s.git_branch IS NOT NULL {date_filter_sessions}
        GROUP BY br
        ORDER BY cnt DESC
        LIMIT 50
    """, b_params)
    branch_rows = await cursor.fetchall()
    branches_list = [
        {"value": str(r[0]), "label": str(r[0]), "count": r[1]}
        for r in branch_rows
    ]

    # Languages (from tool_calls)
    l_params = list(tool_params)
    cursor = await db.execute(f"""
        SELECT COALESCE(tc.language, 'unknown') AS lang,
               COUNT(*) AS cnt
        FROM tool_calls tc
        WHERE tc.language IS NOT NULL AND tc.language != '' {date_filter_tools}
        GROUP BY lang
        ORDER BY cnt DESC
        LIMIT 50
    """, l_params)
    lang_rows = await cursor.fetchall()
    languages = [
        {"value": str(r[0]), "label": str(r[0]), "count": r[1]}
        for r in lang_rows
    ]

    return {
        "projects": projects,
        "models": models_list,
        "branches": branches_list,
        "languages": languages,
    }
