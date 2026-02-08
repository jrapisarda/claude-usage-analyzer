"""Sessions API endpoint."""

import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.common import PaginationMeta
from ccwap.server.models.sessions import SessionsResponse, SessionReplayResponse
from ccwap.server.queries.session_queries import get_sessions, get_session_replay

router = APIRouter(prefix="/api", tags=["sessions"])


@router.get("/sessions", response_model=SessionsResponse)
async def list_sessions(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    project: Optional[str] = None,
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get paginated session list."""
    sessions, total_count = await get_sessions(
        db, date_from, date_to, project, page, limit
    )

    return SessionsResponse(
        sessions=sessions,
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total_count=total_count,
            total_pages=math.ceil(total_count / limit) if limit > 0 else 0,
        ),
    )


@router.get("/sessions/{session_id}/replay", response_model=SessionReplayResponse)
async def session_replay(
    session_id: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get full session replay data with turn-by-turn timeline."""
    result = await get_session_replay(db, session_id)
    if result is None:
        raise HTTPException(status_code=404, detail=f"Session '{session_id}' not found")
    return result
