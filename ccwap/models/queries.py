"""
Named SQL queries for CCWAP.

Centralizes all database queries for maintainability and testing.
"""

# Session queries
GET_SESSION_BY_ID = """
    SELECT * FROM sessions WHERE session_id = ?
"""

GET_SESSIONS_BY_PROJECT = """
    SELECT * FROM sessions
    WHERE project_path = ?
    ORDER BY first_timestamp DESC
"""

GET_SESSIONS_IN_DATE_RANGE = """
    SELECT * FROM sessions
    WHERE date(first_timestamp) >= date(?)
    AND date(first_timestamp) <= date(?)
    ORDER BY first_timestamp DESC
"""

GET_RECENT_SESSIONS = """
    SELECT * FROM sessions
    ORDER BY first_timestamp DESC
    LIMIT ?
"""

# Turn queries
GET_TURNS_BY_SESSION = """
    SELECT * FROM turns
    WHERE session_id = ?
    ORDER BY timestamp ASC
"""

GET_TURN_BY_UUID = """
    SELECT * FROM turns WHERE uuid = ?
"""

COUNT_TURNS_BY_TYPE = """
    SELECT entry_type, COUNT(*) as count
    FROM turns
    WHERE session_id = ?
    GROUP BY entry_type
"""

# Tool call queries
GET_TOOL_CALLS_BY_SESSION = """
    SELECT * FROM tool_calls
    WHERE session_id = ?
    ORDER BY timestamp ASC
"""

GET_TOOL_CALLS_BY_TURN = """
    SELECT * FROM tool_calls
    WHERE turn_id = ?
    ORDER BY id ASC
"""

COUNT_TOOL_CALLS_BY_NAME = """
    SELECT tool_name, COUNT(*) as count,
           SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors
    FROM tool_calls
    GROUP BY tool_name
    ORDER BY count DESC
"""

# Aggregation queries
DAILY_TOTALS = """
    SELECT
        date(timestamp) as date,
        COUNT(DISTINCT session_id) as sessions,
        COUNT(*) as turns,
        SUM(input_tokens) as input_tokens,
        SUM(output_tokens) as output_tokens,
        SUM(cache_read_tokens) as cache_read_tokens,
        SUM(cache_write_tokens) as cache_write_tokens,
        SUM(cost) as cost
    FROM turns
    WHERE date(timestamp) >= date(?)
    AND date(timestamp) <= date(?)
    GROUP BY date(timestamp)
    ORDER BY date DESC
"""

WEEKLY_TOTALS = """
    SELECT
        strftime('%Y-W%W', timestamp) as week,
        COUNT(DISTINCT session_id) as sessions,
        COUNT(*) as turns,
        SUM(input_tokens) as input_tokens,
        SUM(output_tokens) as output_tokens,
        SUM(cache_read_tokens) as cache_read_tokens,
        SUM(cache_write_tokens) as cache_write_tokens,
        SUM(cost) as cost
    FROM turns
    WHERE date(timestamp) >= date(?)
    GROUP BY strftime('%Y-W%W', timestamp)
    ORDER BY week DESC
"""

PROJECT_TOTALS = """
    SELECT
        s.project_path,
        s.project_display,
        COUNT(DISTINCT s.session_id) as sessions,
        COUNT(CASE WHEN s.is_agent = 0 AND t.entry_type IN ('user', 'assistant') THEN 1 END) as messages,
        COUNT(CASE WHEN s.is_agent = 0 AND t.entry_type = 'user' THEN 1 END) as user_turns,
        SUM(t.input_tokens) as input_tokens,
        SUM(t.output_tokens) as output_tokens,
        SUM(t.cache_read_tokens) as cache_read_tokens,
        SUM(t.cache_write_tokens) as cache_write_tokens,
        SUM(t.thinking_chars) as thinking_chars,
        SUM(t.cost) as cost,
        COUNT(CASE WHEN s.is_agent = 1 THEN 1 END) as agent_spawns,
        COUNT(CASE WHEN t.is_meta = 1 THEN 1 END) as skill_invocations,
        SUM(s.duration_seconds) as duration_seconds,
        MAX(s.cc_version) as cc_version,
        MAX(s.git_branch) as git_branch
    FROM sessions s
    LEFT JOIN turns t ON t.session_id = s.session_id
    WHERE 1=1
    {date_filter}
    {project_filter}
    GROUP BY s.project_path, s.project_display
    ORDER BY cost DESC
"""

ALL_TIME_TOTALS = """
    SELECT
        COUNT(DISTINCT session_id) as sessions,
        COUNT(*) as turns,
        SUM(input_tokens) as input_tokens,
        SUM(output_tokens) as output_tokens,
        SUM(cache_read_tokens) as cache_read_tokens,
        SUM(cache_write_tokens) as cache_write_tokens,
        SUM(cost) as cost,
        SUM(thinking_chars) as thinking_chars
    FROM turns
"""

MODEL_BREAKDOWN = """
    SELECT
        model,
        COUNT(*) as turns,
        SUM(input_tokens) as input_tokens,
        SUM(output_tokens) as output_tokens,
        SUM(cache_read_tokens) as cache_read_tokens,
        SUM(cache_write_tokens) as cache_write_tokens,
        SUM(cost) as cost
    FROM turns
    WHERE model IS NOT NULL
    GROUP BY model
    ORDER BY cost DESC
"""

TODAY_TOTALS = """
    SELECT
        COUNT(DISTINCT session_id) as sessions,
        COUNT(*) as turns,
        SUM(input_tokens) as input_tokens,
        SUM(output_tokens) as output_tokens,
        SUM(cost) as cost
    FROM turns
    WHERE date(timestamp) = date('now')
"""

# Tool statistics
TOOL_USAGE_STATS = """
    SELECT
        tool_name,
        COUNT(*) as total_calls,
        SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successful,
        SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failed,
        SUM(loc_written) as loc_written,
        SUM(lines_added) as lines_added,
        SUM(lines_deleted) as lines_deleted
    FROM tool_calls
    GROUP BY tool_name
    ORDER BY total_calls DESC
"""

# Language statistics
LANGUAGE_STATS = """
    SELECT
        language,
        COUNT(*) as file_operations,
        SUM(loc_written) as loc_written,
        SUM(lines_added) as lines_added,
        SUM(lines_deleted) as lines_deleted
    FROM tool_calls
    WHERE language IS NOT NULL
    GROUP BY language
    ORDER BY loc_written DESC
"""

# Error analysis
ERROR_SUMMARY = """
    SELECT
        error_category,
        COUNT(*) as count,
        tool_name
    FROM tool_calls
    WHERE success = 0
    GROUP BY error_category, tool_name
    ORDER BY count DESC
"""

RECENT_ERRORS = """
    SELECT
        tc.tool_name,
        tc.file_path,
        tc.error_category,
        tc.error_message,
        tc.timestamp,
        s.project_display
    FROM tool_calls tc
    JOIN sessions s ON s.session_id = tc.session_id
    WHERE tc.success = 0
    ORDER BY tc.timestamp DESC
    LIMIT ?
"""

# Experiment tags
GET_SESSIONS_BY_TAG = """
    SELECT s.*
    FROM sessions s
    JOIN experiment_tags et ON et.session_id = s.session_id
    WHERE et.tag_name = ?
"""

COMPARE_TAGS = """
    WITH tag_a AS (
        SELECT
            SUM(t.cost) as cost,
            SUM(t.output_tokens) as output_tokens,
            COUNT(DISTINCT t.session_id) as sessions
        FROM turns t
        JOIN experiment_tags et ON et.session_id = t.session_id
        WHERE et.tag_name = ?
    ),
    tag_b AS (
        SELECT
            SUM(t.cost) as cost,
            SUM(t.output_tokens) as output_tokens,
            COUNT(DISTINCT t.session_id) as sessions
        FROM turns t
        JOIN experiment_tags et ON et.session_id = t.session_id
        WHERE et.tag_name = ?
    )
    SELECT * FROM tag_a, tag_b
"""

# ETL state queries
GET_ETL_STATE = """
    SELECT * FROM etl_state WHERE file_path = ?
"""

UPSERT_ETL_STATE = """
    INSERT OR REPLACE INTO etl_state
    (file_path, last_mtime, last_size, last_byte_offset, last_processed, entries_parsed, parse_errors)
    VALUES (?, ?, ?, ?, ?, ?, ?)
"""

# Hourly activity
HOURLY_ACTIVITY = """
    SELECT
        strftime('%H', timestamp) as hour,
        COUNT(*) as turns,
        SUM(cost) as cost
    FROM turns
    GROUP BY strftime('%H', timestamp)
    ORDER BY hour
"""

# Forecast data
LAST_N_DAYS_COST = """
    SELECT
        date(timestamp) as date,
        SUM(cost) as cost
    FROM turns
    WHERE date(timestamp) >= date('now', ?)
    GROUP BY date(timestamp)
    ORDER BY date
"""
