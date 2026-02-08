"""
Incremental processing for CCWAP ETL pipeline.

Tracks file processing state to avoid re-parsing unchanged files.
"""

import sqlite3
from pathlib import Path
from datetime import datetime, timedelta
from typing import Tuple, Optional


def should_process_file(
    conn: sqlite3.Connection,
    file_path: Path,
    recent_hours: Optional[int] = None
) -> Tuple[bool, int]:
    """
    Check if a file needs processing based on mtime/size.

    Returns (should_process, byte_offset)
    - should_process: True if file has changed
    - byte_offset: Where to start reading (0 for full parse)

    Args:
        conn: Database connection
        file_path: Path to the file to check
        recent_hours: If provided, always process files modified within
                      this many hours (bypasses mtime/size check)

    Note: Currently always returns offset 0 since UUID deduplication
    handles any duplicate entries. Future optimization could track
    byte offset for append-only JSONL files.
    """
    stat = file_path.stat()
    current_mtime = stat.st_mtime
    current_size = stat.st_size

    # Check if file is recent enough to always process
    if recent_hours is not None:
        file_time = datetime.fromtimestamp(current_mtime)
        cutoff = datetime.now() - timedelta(hours=recent_hours)
        if file_time > cutoff:
            # Recent file - always process for real-time updates
            return (True, 0)

    cursor = conn.execute(
        "SELECT last_mtime, last_size FROM etl_state WHERE file_path = ?",
        (str(file_path),)
    )
    row = cursor.fetchone()

    if row is None:
        # New file, process from beginning
        return (True, 0)

    last_mtime, last_size = row['last_mtime'], row['last_size']

    if current_mtime == last_mtime and current_size == last_size:
        # File unchanged
        return (False, 0)

    # File changed, re-parse from beginning
    # UUID deduplication will handle any overlapping entries
    return (True, 0)


def update_file_state(
    conn: sqlite3.Connection,
    file_path: Path,
    entries_parsed: int,
    parse_errors: int = 0
) -> None:
    """
    Update ETL state after processing a file.

    Args:
        conn: Database connection
        file_path: Path to processed file
        entries_parsed: Number of entries parsed
        parse_errors: Number of malformed lines encountered
    """
    stat = file_path.stat()

    conn.execute("""
        INSERT OR REPLACE INTO etl_state
        (file_path, last_mtime, last_size, last_byte_offset, last_processed, entries_parsed, parse_errors)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (
        str(file_path),
        stat.st_mtime,
        stat.st_size,
        stat.st_size,  # byte_offset = file size after full parse
        datetime.now().isoformat(),
        entries_parsed,
        parse_errors
    ))


def get_file_state(
    conn: sqlite3.Connection,
    file_path: Path
) -> Optional[dict]:
    """
    Get ETL state for a file.

    Returns dict with state info or None if file hasn't been processed.
    """
    cursor = conn.execute(
        "SELECT * FROM etl_state WHERE file_path = ?",
        (str(file_path),)
    )
    row = cursor.fetchone()

    if row is None:
        return None

    return dict(row)


def clear_file_state(conn: sqlite3.Connection, file_path: Path) -> None:
    """Remove ETL state for a file (forces re-processing)."""
    conn.execute(
        "DELETE FROM etl_state WHERE file_path = ?",
        (str(file_path),)
    )


def clear_all_state(conn: sqlite3.Connection) -> None:
    """Clear all ETL state (forces full rebuild)."""
    conn.execute("DELETE FROM etl_state")
