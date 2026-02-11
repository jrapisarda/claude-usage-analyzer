"""Settings query module."""

from typing import Dict, Any

import aiosqlite


async def get_db_stats(db: aiosqlite.Connection) -> Dict[str, int]:
    """Get row counts for all tables."""
    tables = [
        "sessions", "turns", "tool_calls", "experiment_tags",
        "daily_summaries", "etl_state", "snapshots",
        "saved_views", "alert_rules",
    ]
    stats = {}
    for table in tables:
        cursor = await db.execute(f"SELECT COUNT(*) FROM {table}")
        row = await cursor.fetchone()
        stats[table] = row[0] if row else 0
    return stats


async def get_etl_status(db: aiosqlite.Connection) -> Dict[str, Any]:
    """Get ETL pipeline status."""
    cursor = await db.execute("""
        SELECT COUNT(*), MAX(last_processed)
        FROM etl_state
    """)
    row = await cursor.fetchone()

    return {
        "files_total": row[0] or 0,
        "files_processed": row[0] or 0,
        "last_run": row[1],
        "database_size_bytes": 0,
    }
