"""
Database loader for CCWAP ETL pipeline.

Handles inserting/upserting data into SQLite with proper deduplication.
Uses batch inserts for performance.
"""

import sqlite3
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime

from ccwap.models.entities import SessionData, TurnData, ToolCallData
from ccwap.cost.calculator import calculate_turn_cost


# Batch size for executemany operations
BATCH_SIZE = 5000


def upsert_session(conn: sqlite3.Connection, session: SessionData) -> None:
    """
    Insert or update session record.

    Uses INSERT OR REPLACE for upsert behavior.
    """
    conn.execute("""
        INSERT OR REPLACE INTO sessions (
            session_id, project_path, project_display, first_timestamp,
            last_timestamp, duration_seconds, cc_version, git_branch,
            cwd, is_agent, parent_session_id, file_path, file_mtime, file_size
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        session.session_id,
        session.project_path,
        session.project_display,
        session.first_timestamp.isoformat() if session.first_timestamp else None,
        session.last_timestamp.isoformat() if session.last_timestamp else None,
        session.duration_seconds,
        session.cc_version,
        session.git_branch,
        session.cwd,
        1 if session.is_agent else 0,
        session.parent_session_id,
        str(session.file_path),
        session.file_mtime,
        session.file_size,
    ))


def upsert_turns_batch(
    conn: sqlite3.Connection,
    turns: List[TurnData],
    config: Dict[str, Any]
) -> int:
    """
    Batch insert turns with UUID deduplication.

    Uses INSERT OR IGNORE to skip duplicates by UUID.
    Calculates cost for each turn using its specific model.

    FIXES BUG 6: Each turn uses its OWN model for cost calculation.

    Returns count of newly inserted turns.
    """
    data = []
    pricing_version = config.get('pricing_version', 'unknown')

    for turn in turns:
        # Calculate cost for this turn using ITS model
        cost = calculate_turn_cost(
            turn.usage.input_tokens,
            turn.usage.output_tokens,
            turn.usage.cache_read_tokens,
            turn.usage.cache_write_tokens,
            turn.model,
            config,
            turn.usage.ephemeral_5m_tokens,
            turn.usage.ephemeral_1h_tokens,
        )
        turn.cost = cost
        turn.pricing_version = pricing_version

        data.append((
            turn.session_id,
            turn.uuid,
            turn.parent_uuid,
            turn.timestamp.isoformat() if turn.timestamp else None,
            turn.entry_type,
            turn.model,
            turn.usage.input_tokens,
            turn.usage.output_tokens,
            turn.usage.cache_read_tokens,
            turn.usage.cache_write_tokens,
            turn.usage.ephemeral_5m_tokens,
            turn.usage.ephemeral_1h_tokens,
            cost,
            pricing_version,
            turn.stop_reason,
            turn.service_tier,
            1 if turn.is_sidechain else 0,
            1 if turn.is_meta else 0,
            turn.source_tool_use_id,
            turn.thinking_chars,
            turn.user_type,
            turn.user_prompt_preview,
        ))

    # Batch insert
    inserted = 0
    for i in range(0, len(data), BATCH_SIZE):
        batch = data[i:i + BATCH_SIZE]
        cursor = conn.executemany("""
            INSERT OR IGNORE INTO turns (
                session_id, uuid, parent_uuid, timestamp, entry_type,
                model, input_tokens, output_tokens, cache_read_tokens,
                cache_write_tokens, ephemeral_5m_tokens, ephemeral_1h_tokens,
                cost, pricing_version, stop_reason, service_tier, is_sidechain,
                is_meta, source_tool_use_id, thinking_chars, user_type,
                user_prompt_preview
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, batch)
        inserted += cursor.rowcount

    return inserted


def get_turn_id_by_uuid(conn: sqlite3.Connection, uuid: str) -> Optional[int]:
    """Get the database ID for a turn by its UUID."""
    cursor = conn.execute(
        "SELECT id FROM turns WHERE uuid = ?",
        (uuid,)
    )
    row = cursor.fetchone()
    return row[0] if row else None


def upsert_tool_calls_batch(
    conn: sqlite3.Connection,
    tool_calls: List[ToolCallData],
    turn_id: int,
    session_id: str
) -> int:
    """
    Batch insert tool calls for a turn with deduplication.

    Uses INSERT OR IGNORE to skip duplicates by tool_use_id.

    Args:
        conn: Database connection
        tool_calls: List of ToolCallData objects
        turn_id: Database ID of the parent turn
        session_id: Session ID for denormalized access

    Returns:
        Number of tool calls inserted
    """
    if not tool_calls:
        return 0

    data = []
    for tc in tool_calls:
        data.append((
            turn_id,
            session_id,
            tc.tool_use_id,
            tc.tool_name,
            tc.file_path,
            tc.input_size,
            tc.output_size,
            1 if tc.success else 0,
            tc.error_message[:500] if tc.error_message else None,
            tc.error_category,
            tc.command_name,
            tc.loc_written,
            tc.lines_added,
            tc.lines_deleted,
            tc.language,
            tc.timestamp.isoformat() if tc.timestamp else None,
        ))

    cursor = conn.executemany("""
        INSERT OR IGNORE INTO tool_calls (
            turn_id, session_id, tool_use_id, tool_name, file_path,
            input_size, output_size, success, error_message, error_category,
            command_name, loc_written, lines_added, lines_deleted,
            language, timestamp
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, data)

    return cursor.rowcount


def materialize_daily_summaries(
    conn: sqlite3.Connection,
    affected_dates: Optional[List[str]] = None
) -> int:
    """
    Materialize daily_summaries table from turns and tool_calls.

    Uses the two-query pattern to avoid cross-product JOIN inflation:
    - Query 1: turns aggregates (sessions, messages, tokens, cost)
    - Query 2: tool_calls aggregates (tool_calls, errors, LOC)
    - Query 3: agent/skill counts from sessions/turns

    Args:
        conn: Database connection
        affected_dates: If provided, only recompute these dates (YYYY-MM-DD).
                       If None, recompute all dates.

    Returns:
        Number of dates upserted
    """
    date_filter = ""
    params: list = []

    if affected_dates:
        placeholders = ','.join('?' for _ in affected_dates)
        date_filter = f" AND date(t.timestamp, 'localtime') IN ({placeholders})"
        params = list(affected_dates)

    # Query 1: Turns aggregates (sessions, messages, tokens, cost, thinking)
    turn_params = list(params)
    turns_query = f"""
        SELECT
            date(t.timestamp, 'localtime') as date,
            COUNT(DISTINCT t.session_id) as sessions,
            COUNT(*) as messages,
            COUNT(CASE WHEN t.entry_type = 'user' THEN 1 END) as user_turns,
            SUM(t.input_tokens) as input_tokens,
            SUM(t.output_tokens) as output_tokens,
            SUM(t.cache_read_tokens) as cache_read_tokens,
            SUM(t.cache_write_tokens) as cache_write_tokens,
            SUM(t.thinking_chars) as thinking_chars,
            SUM(t.cost) as cost
        FROM turns t
        WHERE t.timestamp IS NOT NULL {date_filter}
        GROUP BY date(t.timestamp, 'localtime')
    """
    cursor = conn.execute(turns_query, turn_params)
    turns_by_date = {row[0]: dict(zip(
        ['date', 'sessions', 'messages', 'user_turns', 'input_tokens',
         'output_tokens', 'cache_read_tokens', 'cache_write_tokens',
         'thinking_chars', 'cost'],
        row
    )) for row in cursor.fetchall()}

    # Query 2: Tool calls aggregates (tool_calls, errors, LOC, files)
    tc_date_filter = ""
    tc_params: list = []
    if affected_dates:
        placeholders = ','.join('?' for _ in affected_dates)
        tc_date_filter = f" AND date(tc.timestamp, 'localtime') IN ({placeholders})"
        tc_params = list(affected_dates)

    tc_query = f"""
        SELECT
            date(tc.timestamp, 'localtime') as date,
            COUNT(*) as tool_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as errors,
            SUM(tc.loc_written) as loc_written,
            SUM(tc.lines_added) as lines_added,
            SUM(tc.lines_deleted) as lines_deleted,
            COUNT(DISTINCT CASE WHEN tc.tool_name = 'Write' THEN tc.file_path END) as files_created,
            COUNT(DISTINCT CASE WHEN tc.tool_name = 'Edit' THEN tc.file_path END) as files_edited
        FROM tool_calls tc
        WHERE tc.timestamp IS NOT NULL {tc_date_filter}
        GROUP BY date(tc.timestamp, 'localtime')
    """
    cursor = conn.execute(tc_query, tc_params)
    tc_by_date = {row[0]: dict(zip(
        ['date', 'tool_calls', 'errors', 'loc_written', 'lines_added',
         'lines_deleted', 'files_created', 'files_edited'],
        row
    )) for row in cursor.fetchall()}

    # Query 3: Agent spawns and skill invocations
    agent_date_filter = ""
    agent_params: list = []
    if affected_dates:
        placeholders = ','.join('?' for _ in affected_dates)
        agent_date_filter = f" AND date(s.first_timestamp, 'localtime') IN ({placeholders})"
        agent_params = list(affected_dates)

    agent_query = f"""
        SELECT
            date(s.first_timestamp, 'localtime') as date,
            COUNT(CASE WHEN s.is_agent = 1 THEN 1 END) as agent_spawns
        FROM sessions s
        WHERE s.first_timestamp IS NOT NULL {agent_date_filter}
        GROUP BY date(s.first_timestamp, 'localtime')
    """
    cursor = conn.execute(agent_query, agent_params)
    agents_by_date = {row[0]: row[1] for row in cursor.fetchall()}

    skill_date_filter = ""
    skill_params: list = []
    if affected_dates:
        placeholders = ','.join('?' for _ in affected_dates)
        skill_date_filter = f" AND date(t.timestamp, 'localtime') IN ({placeholders})"
        skill_params = list(affected_dates)

    skill_query = f"""
        SELECT
            date(t.timestamp, 'localtime') as date,
            COUNT(CASE WHEN t.is_meta = 1 THEN 1 END) as skill_invocations
        FROM turns t
        WHERE t.timestamp IS NOT NULL {skill_date_filter}
        GROUP BY date(t.timestamp, 'localtime')
    """
    cursor = conn.execute(skill_query, skill_params)
    skills_by_date = {row[0]: row[1] for row in cursor.fetchall()}

    # Merge all dates
    all_dates = set(turns_by_date.keys()) | set(tc_by_date.keys())

    # Build upsert data
    rows = []
    for d in sorted(all_dates):
        t = turns_by_date.get(d, {})
        tc = tc_by_date.get(d, {})

        tool_calls_count = tc.get('tool_calls', 0) or 0
        errors_count = tc.get('errors', 0) or 0
        error_rate = errors_count / tool_calls_count if tool_calls_count > 0 else 0.0
        lines_added = tc.get('lines_added', 0) or 0
        lines_deleted = tc.get('lines_deleted', 0) or 0
        loc_delivered = lines_added - lines_deleted

        rows.append((
            d,
            t.get('sessions', 0) or 0,
            t.get('messages', 0) or 0,
            t.get('user_turns', 0) or 0,
            tool_calls_count,
            errors_count,
            error_rate,
            tc.get('loc_written', 0) or 0,
            loc_delivered,
            lines_added,
            lines_deleted,
            tc.get('files_created', 0) or 0,
            tc.get('files_edited', 0) or 0,
            t.get('input_tokens', 0) or 0,
            t.get('output_tokens', 0) or 0,
            t.get('cache_read_tokens', 0) or 0,
            t.get('cache_write_tokens', 0) or 0,
            t.get('thinking_chars', 0) or 0,
            t.get('cost', 0) or 0,
            agents_by_date.get(d, 0) or 0,
            skills_by_date.get(d, 0) or 0,
        ))

    if rows:
        conn.executemany("""
            INSERT OR REPLACE INTO daily_summaries (
                date, sessions, messages, user_turns, tool_calls, errors,
                error_rate, loc_written, loc_delivered, lines_added,
                lines_deleted, files_created, files_edited, input_tokens,
                output_tokens, cache_read_tokens, cache_write_tokens,
                thinking_chars, cost, agent_spawns, skill_invocations
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, rows)

    return len(rows)


def refresh_materialized_analytics_tables(conn: sqlite3.Connection) -> Dict[str, int]:
    """
    Rebuild optional daily aggregate tables used by Explorer materialized mode.

    This keeps `*_agg_daily` tables synchronized after ETL runs so metrics like
    LOC by model remain up-to-date without requiring a separate backfill step.

    Returns:
        Dict with row counts for each materialized table.
    """
    conn.execute("DELETE FROM turns_agg_daily")
    conn.execute("""
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

    conn.execute("DELETE FROM tool_calls_agg_daily")
    conn.execute("""
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

    conn.execute("DELETE FROM sessions_agg_daily")
    conn.execute("""
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

    counts = {}
    for table in ("turns_agg_daily", "tool_calls_agg_daily", "sessions_agg_daily"):
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        counts[table] = int(row[0] if row else 0)
    return counts


def delete_tool_calls_for_session(conn: sqlite3.Connection, session_id: str) -> int:
    """Delete all tool calls for a session (for re-processing)."""
    cursor = conn.execute(
        "DELETE FROM tool_calls WHERE session_id = ?",
        (session_id,)
    )
    return cursor.rowcount


def get_session_stats(conn: sqlite3.Connection, session_id: str) -> Dict[str, Any]:
    """
    Get aggregated statistics for a session.

    Returns dict with cost, tokens, turn counts, etc.
    """
    cursor = conn.execute("""
        SELECT
            COUNT(*) as turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(cache_write_tokens) as cache_write_tokens,
            SUM(cost) as cost,
            SUM(thinking_chars) as thinking_chars,
            COUNT(CASE WHEN entry_type = 'user' THEN 1 END) as user_turns,
            COUNT(CASE WHEN entry_type = 'assistant' THEN 1 END) as assistant_turns
        FROM turns
        WHERE session_id = ?
    """, (session_id,))

    row = cursor.fetchone()
    return dict(row) if row else {}
