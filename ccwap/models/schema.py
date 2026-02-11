"""
SQLite database schema definition, migrations, and connection management.

This module defines the 7-table schema for CCWAP with proper indexes
and implements versioned migrations using PRAGMA user_version.
"""

import sqlite3
from pathlib import Path
from typing import Optional

# Current schema version - increment when adding migrations
CURRENT_SCHEMA_VERSION = 6


def get_connection(db_path: Path) -> sqlite3.Connection:
    """
    Get a database connection with proper configuration.

    Configures:
    - WAL mode for concurrent reads
    - NORMAL synchronous for balance of safety/speed
    - Row factory for dict-like access
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row

    # Configure for performance and concurrency
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA synchronous=NORMAL")
    conn.execute("PRAGMA cache_size=-64000")  # 64MB cache
    conn.execute("PRAGMA temp_store=MEMORY")
    conn.execute("PRAGMA foreign_keys=ON")

    return conn


def get_schema_version(conn: sqlite3.Connection) -> int:
    """Get current schema version from PRAGMA user_version."""
    cursor = conn.execute("PRAGMA user_version")
    return cursor.fetchone()[0]


def set_schema_version(conn: sqlite3.Connection, version: int) -> None:
    """Set schema version using PRAGMA user_version."""
    conn.execute(f"PRAGMA user_version = {version}")


def ensure_database(conn: sqlite3.Connection) -> None:
    """
    Ensure database has correct schema, running migrations if needed.

    Creates all tables and indexes if they don't exist,
    then runs any pending migrations.
    """
    current_version = get_schema_version(conn)

    if current_version < 1:
        _create_initial_schema(conn)
        set_schema_version(conn, 1)
        conn.commit()

    # Migration v1 -> v2: Add unique constraint on tool_use_id and deduplicate
    if current_version < 2:
        _migrate_v1_to_v2(conn)
        set_schema_version(conn, 2)
        conn.commit()

    # Migration v2 -> v3: Add user_prompt_preview to turns
    if current_version < 3:
        _migrate_v2_to_v3(conn)
        set_schema_version(conn, 3)
        conn.commit()

    # Migration v3 -> v4: Add tag_definitions table for smart tags
    if current_version < 4:
        _migrate_v3_to_v4(conn)
        set_schema_version(conn, 4)
        conn.commit()

    # Migration v4 -> v5: Add optional materialized aggregate tables for analytics explorer
    if current_version < 5:
        _migrate_v4_to_v5(conn)
        set_schema_version(conn, 5)
        conn.commit()

    # Migration v5 -> v6: Add persisted saved views and alert rules
    if current_version < 6:
        _migrate_v5_to_v6(conn)
        set_schema_version(conn, 6)
        conn.commit()


def _create_initial_schema(conn: sqlite3.Connection) -> None:
    """Create the initial schema (version 1)."""

    # Sessions table - session metadata
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions (
            session_id TEXT PRIMARY KEY,
            project_path TEXT NOT NULL,
            project_display TEXT,
            first_timestamp TEXT NOT NULL,
            last_timestamp TEXT,
            duration_seconds INTEGER DEFAULT 0,
            cc_version TEXT,
            git_branch TEXT,
            cwd TEXT,
            is_agent INTEGER DEFAULT 0,
            parent_session_id TEXT,
            file_path TEXT NOT NULL,
            file_mtime REAL,
            file_size INTEGER,
            FOREIGN KEY (parent_session_id) REFERENCES sessions(session_id)
        )
    """)

    # Turns table - individual JSONL entries with token usage
    conn.execute("""
        CREATE TABLE IF NOT EXISTS turns (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            session_id TEXT NOT NULL,
            uuid TEXT UNIQUE NOT NULL,
            parent_uuid TEXT,
            timestamp TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            model TEXT,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            ephemeral_5m_tokens INTEGER DEFAULT 0,
            ephemeral_1h_tokens INTEGER DEFAULT 0,
            cost REAL DEFAULT 0,
            pricing_version TEXT,
            stop_reason TEXT,
            service_tier TEXT,
            is_sidechain INTEGER DEFAULT 0,
            is_meta INTEGER DEFAULT 0,
            source_tool_use_id TEXT,
            thinking_chars INTEGER DEFAULT 0,
            user_type TEXT,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    # Tool calls table - tool invocations with success/error tracking
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tool_calls (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            turn_id INTEGER NOT NULL,
            session_id TEXT NOT NULL,
            tool_use_id TEXT,
            tool_name TEXT NOT NULL,
            file_path TEXT,
            input_size INTEGER DEFAULT 0,
            output_size INTEGER DEFAULT 0,
            success INTEGER DEFAULT 1,
            error_message TEXT,
            error_category TEXT,
            command_name TEXT,
            loc_written INTEGER DEFAULT 0,
            lines_added INTEGER DEFAULT 0,
            lines_deleted INTEGER DEFAULT 0,
            language TEXT,
            timestamp TEXT,
            FOREIGN KEY (turn_id) REFERENCES turns(id),
            FOREIGN KEY (session_id) REFERENCES sessions(session_id)
        )
    """)

    # Experiment tags table - user-defined labels for sessions
    conn.execute("""
        CREATE TABLE IF NOT EXISTS experiment_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            tag_name TEXT NOT NULL,
            session_id TEXT NOT NULL,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (session_id) REFERENCES sessions(session_id),
            UNIQUE(tag_name, session_id)
        )
    """)

    # Tag definitions table - stored criteria for smart/dynamic tags
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tag_definitions (
            tag_name TEXT PRIMARY KEY,
            description TEXT,
            date_from TEXT,
            date_to TEXT,
            project_path TEXT,
            cc_version TEXT,
            model TEXT,
            min_cost REAL,
            max_cost REAL,
            min_loc INTEGER,
            max_loc INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)

    # Daily summaries table - materialized aggregates
    conn.execute("""
        CREATE TABLE IF NOT EXISTS daily_summaries (
            date TEXT PRIMARY KEY,
            sessions INTEGER DEFAULT 0,
            messages INTEGER DEFAULT 0,
            user_turns INTEGER DEFAULT 0,
            tool_calls INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            error_rate REAL DEFAULT 0,
            loc_written INTEGER DEFAULT 0,
            loc_delivered INTEGER DEFAULT 0,
            lines_added INTEGER DEFAULT 0,
            lines_deleted INTEGER DEFAULT 0,
            files_created INTEGER DEFAULT 0,
            files_edited INTEGER DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            thinking_chars INTEGER DEFAULT 0,
            cost REAL DEFAULT 0,
            agent_spawns INTEGER DEFAULT 0,
            skill_invocations INTEGER DEFAULT 0
        )
    """)

    # ETL state table - file processing tracking with byte offset
    conn.execute("""
        CREATE TABLE IF NOT EXISTS etl_state (
            file_path TEXT PRIMARY KEY,
            last_mtime REAL,
            last_size INTEGER,
            last_byte_offset INTEGER DEFAULT 0,
            last_processed TEXT,
            entries_parsed INTEGER DEFAULT 0,
            parse_errors INTEGER DEFAULT 0
        )
    """)

    # Snapshots table - snapshot metadata for --diff feature
    conn.execute("""
        CREATE TABLE IF NOT EXISTS snapshots (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT NOT NULL,
            file_path TEXT NOT NULL,
            tags TEXT,
            summary_json TEXT
        )
    """)

    # Create indexes for query performance
    _create_indexes(conn)


def _create_indexes(conn: sqlite3.Connection) -> None:
    """Create all required indexes for query performance."""

    # Sessions indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_project_path
        ON sessions(project_path)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_first_timestamp
        ON sessions(first_timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_is_agent
        ON sessions(is_agent)
    """)

    # Turns indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_turns_session_id
        ON turns(session_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_turns_timestamp
        ON turns(timestamp)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_turns_entry_type
        ON turns(entry_type)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_turns_session_timestamp
        ON turns(session_id, timestamp)
    """)

    # Tool calls indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_calls_session_id
        ON tool_calls(session_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_calls_turn_id
        ON tool_calls(turn_id)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_calls_tool_name
        ON tool_calls(tool_name)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_calls_success
        ON tool_calls(success)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_calls_timestamp
        ON tool_calls(timestamp)
    """)

    # Experiment tags indexes
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_experiment_tags_tag_name
        ON experiment_tags(tag_name)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_experiment_tags_session_id
        ON experiment_tags(session_id)
    """)

    # Daily summaries index on cost for sorting
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_daily_summaries_cost
        ON daily_summaries(cost)
    """)


def _migrate_v1_to_v2(conn: sqlite3.Connection) -> None:
    """
    Migration v1 -> v2: Fix tool_calls duplication.

    - Remove duplicate tool_calls (keeping only the first by id)
    - Add unique index on tool_use_id to prevent future duplicates
    """
    # First, delete duplicate tool_calls keeping the one with lowest id
    conn.execute("""
        DELETE FROM tool_calls
        WHERE id NOT IN (
            SELECT MIN(id)
            FROM tool_calls
            WHERE tool_use_id IS NOT NULL
            GROUP BY tool_use_id
        )
        AND tool_use_id IS NOT NULL
    """)

    # Add unique index on tool_use_id (NULL values are allowed and don't conflict)
    conn.execute("""
        CREATE UNIQUE INDEX IF NOT EXISTS idx_tool_calls_tool_use_id_unique
        ON tool_calls(tool_use_id)
        WHERE tool_use_id IS NOT NULL
    """)


def _migrate_v2_to_v3(conn: sqlite3.Connection) -> None:
    """
    Migration v2 -> v3: Add user_prompt_preview column to turns table.

    Stores the first 500 characters of user message content for session replay.
    """
    # Check if column already exists (safe for re-runs)
    cursor = conn.execute("PRAGMA table_info(turns)")
    columns = [row[1] for row in cursor.fetchall()]
    if 'user_prompt_preview' not in columns:
        conn.execute("""
            ALTER TABLE turns ADD COLUMN user_prompt_preview TEXT DEFAULT NULL
        """)


def _migrate_v3_to_v4(conn: sqlite3.Connection) -> None:
    """
    Migration v3 -> v4: Add tag_definitions table for smart tags.

    Stores filter criteria for dynamic tag evaluation. Existing
    experiment_tags rows are preserved for manual session additions.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tag_definitions (
            tag_name TEXT PRIMARY KEY,
            description TEXT,
            date_from TEXT,
            date_to TEXT,
            project_path TEXT,
            cc_version TEXT,
            model TEXT,
            min_cost REAL,
            max_cost REAL,
            min_loc INTEGER,
            max_loc INTEGER,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)


def _migrate_v4_to_v5(conn: sqlite3.Connection) -> None:
    """
    Migration v4 -> v5: Add optional materialized aggregate tables.

    These tables are intentionally separate from the canonical source tables and
    are populated by an explicit backfill job behind a feature flag.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS turns_agg_daily (
            date TEXT NOT NULL,
            model TEXT NOT NULL,
            project TEXT NOT NULL,
            branch TEXT NOT NULL,
            cc_version TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            is_agent TEXT NOT NULL,
            cost REAL DEFAULT 0,
            input_tokens INTEGER DEFAULT 0,
            output_tokens INTEGER DEFAULT 0,
            cache_read_tokens INTEGER DEFAULT 0,
            cache_write_tokens INTEGER DEFAULT 0,
            ephemeral_5m_tokens INTEGER DEFAULT 0,
            ephemeral_1h_tokens INTEGER DEFAULT 0,
            thinking_chars INTEGER DEFAULT 0,
            turns_count INTEGER DEFAULT 0,
            PRIMARY KEY (date, model, project, branch, cc_version, entry_type, is_agent)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS tool_calls_agg_daily (
            date TEXT NOT NULL,
            model TEXT NOT NULL,
            project TEXT NOT NULL,
            branch TEXT NOT NULL,
            language TEXT NOT NULL,
            tool_name TEXT NOT NULL,
            cc_version TEXT NOT NULL,
            entry_type TEXT NOT NULL,
            is_agent TEXT NOT NULL,
            loc_written INTEGER DEFAULT 0,
            tool_calls_count INTEGER DEFAULT 0,
            errors INTEGER DEFAULT 0,
            lines_added INTEGER DEFAULT 0,
            lines_deleted INTEGER DEFAULT 0,
            PRIMARY KEY (date, model, project, branch, language, tool_name, cc_version, entry_type, is_agent)
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS sessions_agg_daily (
            date TEXT NOT NULL,
            project TEXT NOT NULL,
            branch TEXT NOT NULL,
            cc_version TEXT NOT NULL,
            is_agent TEXT NOT NULL,
            sessions_count INTEGER DEFAULT 0,
            duration_seconds INTEGER DEFAULT 0,
            PRIMARY KEY (date, project, branch, cc_version, is_agent)
        )
    """)

    # Date-leading indexes for range scans.
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_turns_agg_daily_date
        ON turns_agg_daily(date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tool_calls_agg_daily_date
        ON tool_calls_agg_daily(date)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_sessions_agg_daily_date
        ON sessions_agg_daily(date)
    """)


def _migrate_v5_to_v6(conn: sqlite3.Connection) -> None:
    """
    Migration v5 -> v6: Add saved views and alert rules tables.

    Persists reusable UI filters and threshold-based alert configurations.
    """
    conn.execute("""
        CREATE TABLE IF NOT EXISTS saved_views (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            page TEXT NOT NULL,
            filters_json TEXT NOT NULL DEFAULT '{}',
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alert_rules (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            page TEXT NOT NULL,
            metric TEXT NOT NULL,
            operator TEXT NOT NULL,
            threshold REAL NOT NULL,
            filters_json TEXT NOT NULL DEFAULT '{}',
            enabled INTEGER NOT NULL DEFAULT 1,
            created_at TEXT DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_saved_views_page
        ON saved_views(page)
    """)
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_alert_rules_page_enabled
        ON alert_rules(page, enabled)
    """)


def drop_all_tables(conn: sqlite3.Connection) -> None:
    """Drop all tables (for testing or rebuild)."""
    tables = [
        "snapshots",
        "etl_state",
        "daily_summaries",
        "sessions_agg_daily",
        "alert_rules",
        "saved_views",
        "tool_calls_agg_daily",
        "turns_agg_daily",
        "tag_definitions",
        "experiment_tags",
        "tool_calls",
        "turns",
        "sessions",
    ]
    for table in tables:
        conn.execute(f"DROP TABLE IF EXISTS {table}")
    set_schema_version(conn, 0)
    conn.commit()
