#!/usr/bin/env python3
"""
Snowflake Sync for CCWAP — transfers SQLite analytics data to Snowflake.

Supports incremental sync (tracks watermarks per table) and full reload.
Uses RSA key-pair authentication via environment variables.

Usage:
    python snowflake_sync.py                    # Incremental sync
    python snowflake_sync.py --full-reload      # Drop/recreate, sync from scratch
    python snowflake_sync.py --dry-run          # Preview without writing
    python snowflake_sync.py --status           # Show sync state
    python snowflake_sync.py --tables turns     # Sync specific table(s)

Environment variables required:
    SNOWFLAKE_ACCOUNT               Account identifier
    SNOWFLAKE_USER                  Username
    SNOWFLAKE_PRIVATE_KEY_PATH      Path to RSA private key PEM file
    SNOWFLAKE_WAREHOUSE             Warehouse name
    SNOWFLAKE_DATABASE              Target database
    SNOWFLAKE_SCHEMA                Target schema
    SNOWFLAKE_ROLE                  (optional) Role (default: SYSADMIN)
    SNOWFLAKE_PRIVATE_KEY_PASSPHRASE  (optional) Key passphrase

Dependencies (install separately):
    python -m pip install snowflake-connector-python cryptography
"""

import argparse
import os
import sqlite3
import sys
import time
from pathlib import Path


def load_dotenv(env_path: Path = None):
    """Load variables from a .env file into os.environ (won't overwrite existing)."""
    if env_path is None:
        env_path = Path(__file__).resolve().parent / '.env'
    if not env_path.exists():
        return
    with open(env_path, 'r', encoding='utf-8') as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith('#'):
                continue
            if '=' not in line:
                continue
            key, _, value = line.partition('=')
            key = key.strip()
            value = value.strip()
            # Strip surrounding quotes
            if len(value) >= 2 and value[0] == value[-1] and value[0] in ('"', "'"):
                value = value[1:-1]
            if key not in os.environ:
                os.environ[key] = value


load_dotenv()

try:
    import snowflake.connector
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.backends import default_backend
except ImportError:
    print(
        "Missing dependencies. Install with:\n"
        "  python -m pip install snowflake-connector-python cryptography"
    )
    sys.exit(1)

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DEFAULT_BATCH_SIZE = 5000
MAX_RETRIES = 3
RETRY_BACKOFF_BASE = 2  # seconds

# Sync order respects FK dependencies
SYNC_ORDER = [
    'sessions', 'turns', 'tool_calls', 'experiment_tags',
    'daily_summaries', 'etl_state', 'snapshots',
]

# ---------------------------------------------------------------------------
# Centralized table configuration
# ---------------------------------------------------------------------------

TABLE_CONFIG = {
    'sessions': {
        'strategy': 'upsert',
        'primary_key': 'session_id',
        'columns': [
            ('session_id', 'VARCHAR(200)', 'NOT NULL PRIMARY KEY'),
            ('project_path', 'VARCHAR(1000)', 'NOT NULL'),
            ('project_display', 'VARCHAR(500)', ''),
            ('first_timestamp', 'VARCHAR(50)', 'NOT NULL'),
            ('last_timestamp', 'VARCHAR(50)', ''),
            ('duration_seconds', 'INTEGER', 'DEFAULT 0'),
            ('cc_version', 'VARCHAR(50)', ''),
            ('git_branch', 'VARCHAR(200)', ''),
            ('cwd', 'VARCHAR(1000)', ''),
            ('is_agent', 'INTEGER', 'DEFAULT 0'),
            ('parent_session_id', 'VARCHAR(200)', ''),
            ('file_path', 'VARCHAR(1000)', 'NOT NULL'),
            ('file_mtime', 'FLOAT', ''),
            ('file_size', 'INTEGER', ''),
        ],
    },
    'turns': {
        'strategy': 'incremental_id',
        'primary_key': 'id',
        'columns': [
            ('id', 'INTEGER', 'NOT NULL PRIMARY KEY'),
            ('session_id', 'VARCHAR(200)', 'NOT NULL'),
            ('uuid', 'VARCHAR(200)', 'NOT NULL'),
            ('parent_uuid', 'VARCHAR(200)', ''),
            ('timestamp', 'VARCHAR(50)', 'NOT NULL'),
            ('entry_type', 'VARCHAR(50)', 'NOT NULL'),
            ('model', 'VARCHAR(100)', ''),
            ('input_tokens', 'INTEGER', 'DEFAULT 0'),
            ('output_tokens', 'INTEGER', 'DEFAULT 0'),
            ('cache_read_tokens', 'INTEGER', 'DEFAULT 0'),
            ('cache_write_tokens', 'INTEGER', 'DEFAULT 0'),
            ('ephemeral_5m_tokens', 'INTEGER', 'DEFAULT 0'),
            ('ephemeral_1h_tokens', 'INTEGER', 'DEFAULT 0'),
            ('cost', 'FLOAT', 'DEFAULT 0'),
            ('pricing_version', 'VARCHAR(50)', ''),
            ('stop_reason', 'VARCHAR(50)', ''),
            ('service_tier', 'VARCHAR(50)', ''),
            ('is_sidechain', 'INTEGER', 'DEFAULT 0'),
            ('is_meta', 'INTEGER', 'DEFAULT 0'),
            ('source_tool_use_id', 'VARCHAR(200)', ''),
            ('thinking_chars', 'INTEGER', 'DEFAULT 0'),
            ('user_type', 'VARCHAR(50)', ''),
            ('user_prompt_preview', 'VARCHAR(1000)', ''),
        ],
    },
    'tool_calls': {
        'strategy': 'incremental_id',
        'primary_key': 'id',
        'columns': [
            ('id', 'INTEGER', 'NOT NULL PRIMARY KEY'),
            ('turn_id', 'INTEGER', 'NOT NULL'),
            ('session_id', 'VARCHAR(200)', 'NOT NULL'),
            ('tool_use_id', 'VARCHAR(200)', ''),
            ('tool_name', 'VARCHAR(100)', 'NOT NULL'),
            ('file_path', 'VARCHAR(1000)', ''),
            ('input_size', 'INTEGER', 'DEFAULT 0'),
            ('output_size', 'INTEGER', 'DEFAULT 0'),
            ('success', 'INTEGER', 'DEFAULT 1'),
            ('error_message', 'VARCHAR(2000)', ''),
            ('error_category', 'VARCHAR(100)', ''),
            ('command_name', 'VARCHAR(200)', ''),
            ('loc_written', 'INTEGER', 'DEFAULT 0'),
            ('lines_added', 'INTEGER', 'DEFAULT 0'),
            ('lines_deleted', 'INTEGER', 'DEFAULT 0'),
            ('language', 'VARCHAR(50)', ''),
            ('timestamp', 'VARCHAR(50)', ''),
        ],
    },
    'experiment_tags': {
        'strategy': 'incremental_id',
        'primary_key': 'id',
        'columns': [
            ('id', 'INTEGER', 'NOT NULL PRIMARY KEY'),
            ('tag_name', 'VARCHAR(200)', 'NOT NULL'),
            ('session_id', 'VARCHAR(200)', 'NOT NULL'),
            ('created_at', 'VARCHAR(50)', ''),
        ],
    },
    'daily_summaries': {
        'strategy': 'full_replace',
        'primary_key': 'date',
        'columns': [
            ('date', 'VARCHAR(10)', 'NOT NULL PRIMARY KEY'),
            ('sessions', 'INTEGER', 'DEFAULT 0'),
            ('messages', 'INTEGER', 'DEFAULT 0'),
            ('user_turns', 'INTEGER', 'DEFAULT 0'),
            ('tool_calls', 'INTEGER', 'DEFAULT 0'),
            ('errors', 'INTEGER', 'DEFAULT 0'),
            ('error_rate', 'FLOAT', 'DEFAULT 0'),
            ('loc_written', 'INTEGER', 'DEFAULT 0'),
            ('loc_delivered', 'INTEGER', 'DEFAULT 0'),
            ('lines_added', 'INTEGER', 'DEFAULT 0'),
            ('lines_deleted', 'INTEGER', 'DEFAULT 0'),
            ('files_created', 'INTEGER', 'DEFAULT 0'),
            ('files_edited', 'INTEGER', 'DEFAULT 0'),
            ('input_tokens', 'INTEGER', 'DEFAULT 0'),
            ('output_tokens', 'INTEGER', 'DEFAULT 0'),
            ('cache_read_tokens', 'INTEGER', 'DEFAULT 0'),
            ('cache_write_tokens', 'INTEGER', 'DEFAULT 0'),
            ('thinking_chars', 'INTEGER', 'DEFAULT 0'),
            ('cost', 'FLOAT', 'DEFAULT 0'),
            ('agent_spawns', 'INTEGER', 'DEFAULT 0'),
            ('skill_invocations', 'INTEGER', 'DEFAULT 0'),
        ],
    },
    'etl_state': {
        'strategy': 'full_replace',
        'primary_key': 'file_path',
        'columns': [
            ('file_path', 'VARCHAR(1000)', 'NOT NULL PRIMARY KEY'),
            ('last_mtime', 'FLOAT', ''),
            ('last_size', 'INTEGER', ''),
            ('last_byte_offset', 'INTEGER', 'DEFAULT 0'),
            ('last_processed', 'VARCHAR(50)', ''),
            ('entries_parsed', 'INTEGER', 'DEFAULT 0'),
            ('parse_errors', 'INTEGER', 'DEFAULT 0'),
        ],
    },
    'snapshots': {
        'strategy': 'incremental_id',
        'primary_key': 'id',
        'columns': [
            ('id', 'INTEGER', 'NOT NULL PRIMARY KEY'),
            ('timestamp', 'VARCHAR(50)', 'NOT NULL'),
            ('file_path', 'VARCHAR(1000)', 'NOT NULL'),
            ('tags', 'VARCHAR(2000)', ''),
            ('summary_json', 'VARCHAR(16777216)', ''),
        ],
    },
}

SYNC_STATE_DDL = """
CREATE TABLE IF NOT EXISTS _sync_state (
    table_name VARCHAR(100) NOT NULL PRIMARY KEY,
    last_synced_id INTEGER,
    last_synced_timestamp VARCHAR(50),
    rows_synced INTEGER DEFAULT 0,
    last_sync_at TIMESTAMP_NTZ DEFAULT CURRENT_TIMESTAMP()
)
"""

# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def load_private_key(key_path: str) -> bytes:
    """Load RSA private key from PEM file, return DER-encoded bytes."""
    path = Path(key_path).expanduser()
    if not path.exists():
        raise FileNotFoundError(f"RSA private key not found at {path}")

    with open(path, 'rb') as f:
        pem_data = f.read()

    passphrase = os.environ.get('SNOWFLAKE_PRIVATE_KEY_PASSPHRASE')
    passphrase_bytes = passphrase.encode() if passphrase else None

    private_key = serialization.load_pem_private_key(
        pem_data,
        password=passphrase_bytes,
        backend=default_backend(),
    )

    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def get_snowflake_connection():
    """Create Snowflake connection using RSA key-pair auth from env vars."""
    required = [
        'SNOWFLAKE_ACCOUNT', 'SNOWFLAKE_USER', 'SNOWFLAKE_PRIVATE_KEY_PATH',
        'SNOWFLAKE_WAREHOUSE', 'SNOWFLAKE_DATABASE', 'SNOWFLAKE_SCHEMA',
    ]
    missing = [v for v in required if not os.environ.get(v)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}"
        )

    private_key_bytes = load_private_key(os.environ['SNOWFLAKE_PRIVATE_KEY_PATH'])

    role = os.environ.get('SNOWFLAKE_ROLE', 'SYSADMIN')

    return snowflake.connector.connect(
        account=os.environ['SNOWFLAKE_ACCOUNT'],
        user=os.environ['SNOWFLAKE_USER'],
        private_key=private_key_bytes,
        warehouse=os.environ['SNOWFLAKE_WAREHOUSE'],
        database=os.environ['SNOWFLAKE_DATABASE'],
        schema=os.environ['SNOWFLAKE_SCHEMA'],
        role=role,
    )


def get_sqlite_connection() -> sqlite3.Connection:
    """Open the CCWAP SQLite database in read-only mode."""
    from ccwap.config.loader import load_config, get_database_path

    config = load_config()
    db_path = get_database_path(config)

    if not db_path.exists():
        raise FileNotFoundError(
            f"CCWAP database not found at {db_path}\n"
            "Run 'python -m ccwap' first to populate the database."
        )

    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


# ---------------------------------------------------------------------------
# Snowflake schema management
# ---------------------------------------------------------------------------

def _build_create_ddl(table_name: str, config: dict) -> str:
    """Build CREATE TABLE IF NOT EXISTS DDL from TABLE_CONFIG."""
    col_defs = []
    for col_name, col_type, constraints in config['columns']:
        parts = [col_name, col_type]
        if constraints:
            parts.append(constraints)
        col_defs.append(' '.join(parts))
    cols_sql = ',\n    '.join(col_defs)
    return f"CREATE TABLE IF NOT EXISTS {table_name} (\n    {cols_sql}\n)"


def _use_database(sf_conn) -> bool:
    """Set session database and schema context. Returns True if successful."""
    db = os.environ['SNOWFLAKE_DATABASE']
    schema = os.environ['SNOWFLAKE_SCHEMA']
    cursor = sf_conn.cursor()
    try:
        cursor.execute(f"USE DATABASE {db}")
        cursor.execute(f"USE SCHEMA {schema}")
        return True
    except snowflake.connector.errors.ProgrammingError:
        return False
    finally:
        cursor.close()


def ensure_snowflake_schema(sf_conn):
    """Create database, schema, and all tables in Snowflake if they don't exist."""
    db = os.environ['SNOWFLAKE_DATABASE']
    schema = os.environ['SNOWFLAKE_SCHEMA']
    cursor = sf_conn.cursor()

    # Try USE first; fall back to CREATE if the database doesn't exist
    try:
        cursor.execute(f"USE DATABASE {db}")
    except snowflake.connector.errors.ProgrammingError:
        cursor.execute(f"CREATE DATABASE IF NOT EXISTS {db}")
        cursor.execute(f"USE DATABASE {db}")

    try:
        cursor.execute(f"USE SCHEMA {schema}")
    except snowflake.connector.errors.ProgrammingError:
        cursor.execute(f"CREATE SCHEMA IF NOT EXISTS {schema}")
        cursor.execute(f"USE SCHEMA {schema}")

    cursor.execute(SYNC_STATE_DDL)
    for table_name, config in TABLE_CONFIG.items():
        cursor.execute(_build_create_ddl(table_name, config))
    cursor.close()


def drop_tables(sf_conn, tables: list):
    """Drop specified tables plus _sync_state for full reload."""
    cursor = sf_conn.cursor()
    # Drop in reverse dependency order
    reverse_order = list(reversed(SYNC_ORDER))
    for table in reverse_order:
        if table in tables:
            cursor.execute(f"DROP TABLE IF EXISTS {table}")
    cursor.execute("DROP TABLE IF EXISTS _sync_state")
    cursor.close()


# ---------------------------------------------------------------------------
# Sync state tracking (_sync_state table)
# ---------------------------------------------------------------------------

def get_sync_state(sf_conn, table_name: str) -> dict:
    """Read the sync watermark for a given table."""
    cursor = sf_conn.cursor()
    try:
        cursor.execute(
            "SELECT last_synced_id, last_synced_timestamp, rows_synced "
            "FROM _sync_state WHERE table_name = %s",
            (table_name,),
        )
        row = cursor.fetchone()
    except snowflake.connector.errors.ProgrammingError:
        # _sync_state table doesn't exist yet (e.g. first dry-run)
        row = None
    cursor.close()
    if row:
        return {
            'last_synced_id': row[0],
            'last_synced_timestamp': row[1],
            'rows_synced': row[2],
        }
    return {'last_synced_id': None, 'last_synced_timestamp': None, 'rows_synced': 0}


def update_sync_state(sf_conn, table_name: str, *,
                      last_synced_id=None, last_synced_timestamp=None,
                      rows_synced=0):
    """Upsert the sync watermark for a table."""
    cursor = sf_conn.cursor()
    cursor.execute(
        "MERGE INTO _sync_state AS t "
        "USING (SELECT %s AS table_name) AS s "
        "ON t.table_name = s.table_name "
        "WHEN MATCHED THEN UPDATE SET "
        "  last_synced_id = %s, "
        "  last_synced_timestamp = %s, "
        "  rows_synced = t.rows_synced + %s, "
        "  last_sync_at = CURRENT_TIMESTAMP() "
        "WHEN NOT MATCHED THEN INSERT "
        "  (table_name, last_synced_id, last_synced_timestamp, rows_synced) "
        "  VALUES (%s, %s, %s, %s)",
        (
            table_name,
            last_synced_id, last_synced_timestamp, rows_synced,
            table_name, last_synced_id, last_synced_timestamp, rows_synced,
        ),
    )
    cursor.close()


# ---------------------------------------------------------------------------
# Retry wrapper
# ---------------------------------------------------------------------------

def execute_with_retry(cursor, sql, params=None, *, many=False):
    """Execute SQL with exponential-backoff retry for transient errors."""
    for attempt in range(MAX_RETRIES + 1):
        try:
            if many:
                cursor.executemany(sql, params)
            elif params:
                cursor.execute(sql, params)
            else:
                cursor.execute(sql)
            return cursor
        except snowflake.connector.errors.ProgrammingError:
            raise  # syntax / schema errors — not retryable
        except (snowflake.connector.errors.OperationalError,
                snowflake.connector.errors.DatabaseError) as e:
            if attempt < MAX_RETRIES:
                wait = RETRY_BACKOFF_BASE ** attempt
                print(f"  Retry {attempt + 1}/{MAX_RETRIES} in {wait}s: {e}")
                time.sleep(wait)
            else:
                raise


# ---------------------------------------------------------------------------
# Progress reporting
# ---------------------------------------------------------------------------

def print_progress(table: str, done: int, total: int, suffix: str = ''):
    """In-place progress update via carriage return."""
    if total == 0:
        sys.stdout.write(f'\r  {table:<20} no new rows to sync')
    else:
        pct = done / total * 100
        sys.stdout.write(
            f'\r  {table:<20} {done:>8,}/{total:,} ({pct:5.1f}%)'
            f'{" — " + suffix if suffix else ""}'
        )
    sys.stdout.flush()
    if done >= total:
        sys.stdout.write('\n')


# ---------------------------------------------------------------------------
# Sync strategies
# ---------------------------------------------------------------------------

def _col_names(config: dict) -> list:
    """Extract column name list from TABLE_CONFIG entry."""
    return [c[0] for c in config['columns']]


def sync_incremental_by_id(sqlite_conn, sf_conn, table_name: str,
                           config: dict, batch_size: int) -> int:
    """Sync rows where id > last_synced_id. For append-only tables."""
    state = get_sync_state(sf_conn, table_name)
    last_id = state['last_synced_id'] or 0

    columns = _col_names(config)
    col_list = ', '.join(columns)

    # Count pending rows
    count_row = sqlite_conn.execute(
        f"SELECT COUNT(*) FROM {table_name} WHERE id > ?", (last_id,)
    ).fetchone()
    total = count_row[0]

    if total == 0:
        print_progress(table_name, 0, 0)
        return 0

    placeholders = ', '.join(['%s'] * len(columns))
    insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

    sqlite_cur = sqlite_conn.execute(
        f"SELECT {col_list} FROM {table_name} WHERE id > ? ORDER BY id",
        (last_id,),
    )

    sf_cur = sf_conn.cursor()
    rows_synced = 0
    max_id = last_id

    while True:
        batch = sqlite_cur.fetchmany(batch_size)
        if not batch:
            break

        rows = [tuple(row) for row in batch]
        try:
            execute_with_retry(sf_cur, insert_sql, rows, many=True)
        except snowflake.connector.errors.IntegrityError as e:
            # PK collision — fall back to row-by-row, skipping dupes
            print(f"\n  {table_name}: PK conflict in batch, inserting row-by-row...")
            for row in rows:
                try:
                    execute_with_retry(sf_cur, insert_sql, row)
                except snowflake.connector.errors.IntegrityError:
                    pass  # skip duplicate

        rows_synced += len(rows)
        max_id = rows[-1][0]  # id is first column
        print_progress(table_name, rows_synced, total,
                       f"ID {last_id + 1} -> {max_id}")

    sf_cur.close()
    update_sync_state(sf_conn, table_name,
                      last_synced_id=max_id, rows_synced=rows_synced)
    return rows_synced


def sync_upsert_sessions(sqlite_conn, sf_conn, batch_size: int) -> int:
    """Sync sessions via temp-table MERGE (handles inserts + updates)."""
    table_name = 'sessions'
    config = TABLE_CONFIG[table_name]
    state = get_sync_state(sf_conn, table_name)
    last_mtime = float(state['last_synced_timestamp'] or '0')

    columns = _col_names(config)
    col_list = ', '.join(columns)

    # Fetch changed sessions (new or updated via re-processed JSONL files)
    sqlite_cur = sqlite_conn.execute(
        f"SELECT {col_list} FROM sessions "
        "WHERE file_mtime > ? OR file_mtime IS NULL "
        "ORDER BY session_id",
        (last_mtime,),
    )
    all_rows = [tuple(row) for row in sqlite_cur.fetchall()]
    total = len(all_rows)

    if total == 0:
        print_progress(table_name, 0, 0)
        return 0

    sf_cur = sf_conn.cursor()

    # Create temp table matching sessions schema
    sf_cur.execute("CREATE TEMPORARY TABLE IF NOT EXISTS _tmp_sessions LIKE sessions")

    placeholders = ', '.join(['%s'] * len(columns))
    tmp_insert = f"INSERT INTO _tmp_sessions ({col_list}) VALUES ({placeholders})"

    non_pk_cols = [c for c in columns if c != 'session_id']
    set_clause = ', '.join(f"target.{c} = source.{c}" for c in non_pk_cols)
    insert_vals = ', '.join(f"source.{c}" for c in columns)

    merge_sql = (
        "MERGE INTO sessions AS target "
        "USING _tmp_sessions AS source "
        "ON target.session_id = source.session_id "
        f"WHEN MATCHED THEN UPDATE SET {set_clause} "
        f"WHEN NOT MATCHED THEN INSERT ({col_list}) VALUES ({insert_vals})"
    )

    rows_synced = 0
    max_mtime = last_mtime

    for i in range(0, total, batch_size):
        batch = all_rows[i:i + batch_size]

        sf_cur.execute("TRUNCATE TABLE _tmp_sessions")
        execute_with_retry(sf_cur, tmp_insert, batch, many=True)
        execute_with_retry(sf_cur, merge_sql)

        # Track max file_mtime in this batch
        # file_mtime is at index of 'file_mtime' in columns
        mtime_idx = columns.index('file_mtime')
        for row in batch:
            mtime = row[mtime_idx]
            if mtime is not None and mtime > max_mtime:
                max_mtime = mtime

        rows_synced += len(batch)
        print_progress(table_name, rows_synced, total)

    sf_cur.execute("DROP TABLE IF EXISTS _tmp_sessions")
    sf_cur.close()

    update_sync_state(sf_conn, table_name,
                      last_synced_timestamp=str(max_mtime),
                      rows_synced=rows_synced)
    return rows_synced


def sync_full_replace(sqlite_conn, sf_conn, table_name: str,
                      config: dict, batch_size: int) -> int:
    """Delete all rows in Snowflake and reload from SQLite."""
    columns = _col_names(config)
    col_list = ', '.join(columns)

    sqlite_cur = sqlite_conn.execute(f"SELECT {col_list} FROM {table_name}")
    all_rows = [tuple(row) for row in sqlite_cur.fetchall()]
    total = len(all_rows)

    sf_cur = sf_conn.cursor()

    # Wrap in transaction so consumers never see empty table
    execute_with_retry(sf_cur, "BEGIN")
    execute_with_retry(sf_cur, f"DELETE FROM {table_name}")

    if total > 0:
        placeholders = ', '.join(['%s'] * len(columns))
        insert_sql = f"INSERT INTO {table_name} ({col_list}) VALUES ({placeholders})"

        rows_done = 0
        for i in range(0, total, batch_size):
            batch = all_rows[i:i + batch_size]
            execute_with_retry(sf_cur, insert_sql, batch, many=True)
            rows_done += len(batch)
            print_progress(table_name, rows_done, total, 'replacing')

    execute_with_retry(sf_cur, "COMMIT")
    sf_cur.close()

    update_sync_state(sf_conn, table_name, rows_synced=total)

    if total == 0:
        print_progress(table_name, 0, 0)

    return total


# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

def sync_table(sqlite_conn, sf_conn, table_name: str,
               batch_size: int) -> int:
    """Dispatch to the correct sync strategy for a table."""
    config = TABLE_CONFIG[table_name]
    strategy = config['strategy']

    if strategy == 'incremental_id':
        return sync_incremental_by_id(sqlite_conn, sf_conn,
                                      table_name, config, batch_size)
    elif strategy == 'upsert':
        return sync_upsert_sessions(sqlite_conn, sf_conn, batch_size)
    elif strategy == 'full_replace':
        return sync_full_replace(sqlite_conn, sf_conn,
                                 table_name, config, batch_size)
    else:
        raise ValueError(f"Unknown sync strategy '{strategy}' for {table_name}")


def get_pending_count(sqlite_conn, sf_conn, table_name: str) -> tuple:
    """Return (count, description) of rows that would be synced."""
    config = TABLE_CONFIG[table_name]
    strategy = config['strategy']

    if strategy == 'incremental_id':
        state = get_sync_state(sf_conn, table_name)
        last_id = state['last_synced_id'] or 0
        count = sqlite_conn.execute(
            f"SELECT COUNT(*) FROM {table_name} WHERE id > ?", (last_id,)
        ).fetchone()[0]
        return count, f"new rows (id > {last_id})"

    elif strategy == 'upsert':
        state = get_sync_state(sf_conn, table_name)
        last_mtime = float(state['last_synced_timestamp'] or '0')
        count = sqlite_conn.execute(
            f"SELECT COUNT(*) FROM {table_name} "
            "WHERE file_mtime > ? OR file_mtime IS NULL",
            (last_mtime,),
        ).fetchone()[0]
        return count, "new/updated rows"

    elif strategy == 'full_replace':
        count = sqlite_conn.execute(
            f"SELECT COUNT(*) FROM {table_name}"
        ).fetchone()[0]
        return count, "rows (full replace)"

    return 0, "unknown strategy"


# ---------------------------------------------------------------------------
# --status command
# ---------------------------------------------------------------------------

def show_status(sf_conn):
    """Print current sync state from _sync_state table."""
    cursor = sf_conn.cursor()
    try:
        cursor.execute(
            "SELECT table_name, last_synced_id, last_synced_timestamp, "
            "rows_synced, last_sync_at "
            "FROM _sync_state ORDER BY table_name"
        )
        rows = cursor.fetchall()
    except snowflake.connector.errors.ProgrammingError:
        print("No sync state found. Run the sync first.")
        cursor.close()
        return

    cursor.close()

    if not rows:
        print("No sync state found. Run the sync first.")
        return

    print("CCWAP Snowflake Sync Status")
    print("=" * 72)
    print(f"{'Table':<20} {'Last ID':>10} {'Last Timestamp':>18} "
          f"{'Rows':>10} {'Last Sync'}")
    print("-" * 72)
    for table_name, last_id, last_ts, rows_synced, last_sync in rows:
        id_str = str(last_id) if last_id is not None else '-'
        ts_str = (last_ts or '-')[:18]
        rows_str = f"{rows_synced:,}" if rows_synced else '0'
        sync_str = str(last_sync)[:19] if last_sync else '-'
        print(f"{table_name:<20} {id_str:>10} {ts_str:>18} "
              f"{rows_str:>10} {sync_str}")


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def create_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog='snowflake_sync',
        description='Sync CCWAP SQLite analytics data to Snowflake.',
        epilog=(
            'Environment variables required:\n'
            '  SNOWFLAKE_ACCOUNT                Account identifier\n'
            '  SNOWFLAKE_USER                   Username\n'
            '  SNOWFLAKE_PRIVATE_KEY_PATH       Path to RSA private key PEM\n'
            '  SNOWFLAKE_WAREHOUSE              Warehouse name\n'
            '  SNOWFLAKE_DATABASE               Target database\n'
            '  SNOWFLAKE_SCHEMA                 Target schema\n'
            '  SNOWFLAKE_ROLE                   (optional) Role (default: SYSADMIN)\n'
            '  SNOWFLAKE_PRIVATE_KEY_PASSPHRASE (optional) Key passphrase\n'
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    parser.add_argument(
        '--full-reload', action='store_true',
        help='Drop and recreate all tables, sync everything from scratch',
    )
    parser.add_argument(
        '--dry-run', action='store_true',
        help='Show what would be synced without writing to Snowflake',
    )
    parser.add_argument(
        '--tables', nargs='+',
        choices=SYNC_ORDER,
        help='Sync only specific tables (default: all)',
    )
    parser.add_argument(
        '--batch-size', type=int, default=DEFAULT_BATCH_SIZE,
        help=f'Batch size for inserts (default: {DEFAULT_BATCH_SIZE})',
    )
    parser.add_argument(
        '--verbose', '-v', action='store_true',
        help='Verbose output',
    )
    parser.add_argument(
        '--status', action='store_true',
        help='Show current sync state and exit',
    )

    return parser


def main():
    parser = create_parser()
    args = parser.parse_args()

    # Connect to Snowflake
    try:
        sf_conn = get_snowflake_connection()
    except (EnvironmentError, FileNotFoundError) as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Snowflake connection failed: {e}")
        sys.exit(1)

    # --status: show state and exit
    if args.status:
        show_status(sf_conn)
        sf_conn.close()
        return

    # Open SQLite
    try:
        sqlite_conn = get_sqlite_connection()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sf_conn.close()
        sys.exit(1)

    # Determine tables to sync (preserve dependency order)
    if args.tables:
        tables_to_sync = [t for t in SYNC_ORDER if t in args.tables]
    else:
        tables_to_sync = list(SYNC_ORDER)

    # Header
    account = os.environ.get('SNOWFLAKE_ACCOUNT', '?')
    database = os.environ.get('SNOWFLAKE_DATABASE', '?')
    schema = os.environ.get('SNOWFLAKE_SCHEMA', '?')

    from ccwap.config.loader import load_config, get_database_path
    db_path = get_database_path(load_config())

    print("CCWAP Snowflake Sync")
    print("=" * 40)
    print(f"Source: {db_path}")
    print(f"Target: {account} / {database}.{schema}")
    print()

    # Set up Snowflake database/schema
    if not args.dry_run:
        ensure_snowflake_schema(sf_conn)

        # --full-reload
        if args.full_reload:
            print("Full reload: dropping and recreating tables...")
            drop_tables(sf_conn, tables_to_sync)
            ensure_snowflake_schema(sf_conn)
            print()
    else:
        _use_database(sf_conn)  # Best-effort; dry-run works even without DB

    # Sync
    start_time = time.time()
    total_rows = 0
    errors = []

    mode = "Dry run" if args.dry_run else "Syncing"
    print(f"{mode}: {len(tables_to_sync)} table(s)...\n")

    for table in tables_to_sync:
        try:
            if args.dry_run:
                count, desc = get_pending_count(sqlite_conn, sf_conn, table)
                print(f"  {table:<20} {count:>8,} {desc}")
            else:
                rows = sync_table(sqlite_conn, sf_conn, table, args.batch_size)
                total_rows += rows
        except Exception as e:
            errors.append((table, str(e)))
            print(f"\n  ERROR syncing {table}: {e}")
            if args.verbose:
                import traceback
                traceback.print_exc()

    elapsed = time.time() - start_time

    # Summary
    print()
    if args.dry_run:
        print(f"Dry run complete in {elapsed:.1f}s")
    else:
        print(f"Sync complete in {elapsed:.1f}s")
        print(f"  Total rows synced: {total_rows:,}")
        print(f"  Errors: {len(errors)}")

    if errors:
        print("\nFailed tables:")
        for table, err in errors:
            print(f"  {table}: {err}")

    sqlite_conn.close()
    sf_conn.close()

    if errors:
        sys.exit(1)


if __name__ == '__main__':
    main()
