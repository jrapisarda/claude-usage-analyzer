"""Helpers for optional materialized analytics aggregates."""

from typing import Any, Dict, Optional

import aiosqlite


def is_materialized_enabled(config: Optional[Dict[str, Any]]) -> bool:
    """Return whether materialized analytics should be used."""
    flags = (config or {}).get("feature_flags", {})
    return bool(flags.get("analytics_materialized_enabled", False))


async def refresh_materialized_analytics(db: aiosqlite.Connection) -> Dict[str, int]:
    """Rebuild materialized explorer aggregate tables from canonical source tables."""
    await db.execute("DELETE FROM turns_agg_daily")
    await db.execute("""
        INSERT INTO turns_agg_daily (
            date, model, project, branch, cc_version, entry_type, is_agent,
            cost, input_tokens, output_tokens, cache_read_tokens, cache_write_tokens,
            ephemeral_5m_tokens, ephemeral_1h_tokens, thinking_chars, turns_count
        )
        SELECT
            date(t.timestamp, 'localtime') AS date,
            COALESCE(t.model, 'unknown') AS model,
            COALESCE(s.project_display, s.project_path) AS project,
            COALESCE(s.git_branch, 'unknown') AS branch,
            COALESCE(s.cc_version, 'unknown') AS cc_version,
            COALESCE(t.entry_type, 'unknown') AS entry_type,
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END AS is_agent,
            COALESCE(SUM(t.cost), 0) AS cost,
            COALESCE(SUM(t.input_tokens), 0) AS input_tokens,
            COALESCE(SUM(t.output_tokens), 0) AS output_tokens,
            COALESCE(SUM(t.cache_read_tokens), 0) AS cache_read_tokens,
            COALESCE(SUM(t.cache_write_tokens), 0) AS cache_write_tokens,
            COALESCE(SUM(t.ephemeral_5m_tokens), 0) AS ephemeral_5m_tokens,
            COALESCE(SUM(t.ephemeral_1h_tokens), 0) AS ephemeral_1h_tokens,
            COALESCE(SUM(t.thinking_chars), 0) AS thinking_chars,
            COUNT(*) AS turns_count
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE t.timestamp IS NOT NULL
        GROUP BY
            date(t.timestamp, 'localtime'),
            COALESCE(t.model, 'unknown'),
            COALESCE(s.project_display, s.project_path),
            COALESCE(s.git_branch, 'unknown'),
            COALESCE(s.cc_version, 'unknown'),
            COALESCE(t.entry_type, 'unknown'),
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END
    """)

    await db.execute("DELETE FROM tool_calls_agg_daily")
    await db.execute("""
        INSERT INTO tool_calls_agg_daily (
            date, model, project, branch, language, tool_name, cc_version, entry_type, is_agent,
            loc_written, tool_calls_count, errors, lines_added, lines_deleted
        )
        SELECT
            date(tc.timestamp, 'localtime') AS date,
            COALESCE(t.model, 'unknown') AS model,
            COALESCE(s.project_display, s.project_path) AS project,
            COALESCE(s.git_branch, 'unknown') AS branch,
            COALESCE(tc.language, 'unknown') AS language,
            COALESCE(tc.tool_name, 'unknown') AS tool_name,
            COALESCE(s.cc_version, 'unknown') AS cc_version,
            COALESCE(t.entry_type, 'unknown') AS entry_type,
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END AS is_agent,
            COALESCE(SUM(tc.loc_written), 0) AS loc_written,
            COUNT(*) AS tool_calls_count,
            COALESCE(SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END), 0) AS errors,
            COALESCE(SUM(tc.lines_added), 0) AS lines_added,
            COALESCE(SUM(tc.lines_deleted), 0) AS lines_deleted
        FROM tool_calls tc
        JOIN sessions s ON tc.session_id = s.session_id
        LEFT JOIN turns t ON tc.turn_id = t.id
        WHERE tc.timestamp IS NOT NULL
        GROUP BY
            date(tc.timestamp, 'localtime'),
            COALESCE(t.model, 'unknown'),
            COALESCE(s.project_display, s.project_path),
            COALESCE(s.git_branch, 'unknown'),
            COALESCE(tc.language, 'unknown'),
            COALESCE(tc.tool_name, 'unknown'),
            COALESCE(s.cc_version, 'unknown'),
            COALESCE(t.entry_type, 'unknown'),
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END
    """)

    await db.execute("DELETE FROM sessions_agg_daily")
    await db.execute("""
        INSERT INTO sessions_agg_daily (
            date, project, branch, cc_version, is_agent,
            sessions_count, duration_seconds
        )
        SELECT
            date(s.first_timestamp, 'localtime') AS date,
            COALESCE(s.project_display, s.project_path) AS project,
            COALESCE(s.git_branch, 'unknown') AS branch,
            COALESCE(s.cc_version, 'unknown') AS cc_version,
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END AS is_agent,
            COUNT(*) AS sessions_count,
            COALESCE(SUM(s.duration_seconds), 0) AS duration_seconds
        FROM sessions s
        WHERE s.first_timestamp IS NOT NULL
        GROUP BY
            date(s.first_timestamp, 'localtime'),
            COALESCE(s.project_display, s.project_path),
            COALESCE(s.git_branch, 'unknown'),
            COALESCE(s.cc_version, 'unknown'),
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END
    """)

    await db.commit()
    return await get_materialized_row_counts(db)


async def get_materialized_row_counts(db: aiosqlite.Connection) -> Dict[str, int]:
    """Return row counts for materialized aggregate tables."""
    counts: Dict[str, int] = {}
    for table in ("turns_agg_daily", "tool_calls_agg_daily", "sessions_agg_daily"):
        cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")  # noqa: S608
        row = await cursor.fetchone()
        counts[table] = int(row[0] or 0) if row else 0
    return counts

