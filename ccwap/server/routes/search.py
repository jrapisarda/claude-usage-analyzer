from typing import Optional
from fastapi import APIRouter, Query, Depends
import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.search import SearchResponse, SearchResult
from ccwap.server.queries.search_queries import search_all

router = APIRouter(prefix="/api", tags=["search"])


@router.get("/search", response_model=SearchResponse)
async def search(
    q: str = Query("", min_length=0),
    limit: int = Query(5, ge=1, le=20),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Search across all entities for Cmd+K command palette."""
    results = await search_all(db, q, limit)
    return SearchResponse(
        results=[SearchResult(**r) for r in results],
        query=q,
    )
