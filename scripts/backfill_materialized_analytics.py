"""Backfill optional materialized analytics aggregate tables."""

import asyncio

import aiosqlite

from ccwap.config.loader import load_config, get_database_path
from ccwap.models.schema import get_connection, ensure_database
from ccwap.server.queries.materialized_queries import refresh_materialized_analytics


async def _run() -> None:
    config = load_config()
    db_path = get_database_path(config)

    # Ensure latest schema (including materialized tables) exists.
    sync_conn = get_connection(db_path)
    ensure_database(sync_conn)
    sync_conn.close()

    db = await aiosqlite.connect(str(db_path))
    try:
        stats = await refresh_materialized_analytics(db)
    finally:
        await db.close()

    print("Materialized analytics backfill complete:")
    print(f"  turns_agg_daily: {stats['turns_agg_daily']}")
    print(f"  tool_calls_agg_daily: {stats['tool_calls_agg_daily']}")
    print(f"  sessions_agg_daily: {stats['sessions_agg_daily']}")


if __name__ == "__main__":
    asyncio.run(_run())

