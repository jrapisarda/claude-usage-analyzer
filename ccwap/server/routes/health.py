"""Health check endpoint."""

import time
from fastapi import APIRouter, Depends

import aiosqlite

from ccwap.server.dependencies import get_db

router = APIRouter(prefix="/api", tags=["health"])

_start_time = time.time()


@router.get("/health")
async def health_check(db: aiosqlite.Connection = Depends(get_db)):
    """Health check: returns status, uptime, database health."""
    uptime = int(time.time() - _start_time)

    db_status = "ok"
    try:
        cursor = await db.execute("SELECT 1")
        await cursor.fetchone()
    except Exception:
        db_status = "error"

    return {
        "status": "ok",
        "uptime_seconds": uptime,
        "database": db_status,
        "version": "1.0.0",
    }
