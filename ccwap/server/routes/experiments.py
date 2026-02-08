"""Experiments API endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.experiments import (
    TagListResponse,
    TagCreateRequest,
    TagDeleteRequest,
    ComparisonResponse,
)
from ccwap.server.queries.experiment_queries import (
    get_tags,
    create_tag,
    delete_tag,
    compare_tags,
    compare_tags_multi,
    get_tag_sessions,
)

router = APIRouter(prefix="/api", tags=["experiments"])


@router.get("/experiments/tags", response_model=TagListResponse)
async def list_tags(db: aiosqlite.Connection = Depends(get_db)):
    """List all experiment tags."""
    tags = await get_tags(db)
    return TagListResponse(tags=tags)


@router.post("/experiments/tags")
async def create_experiment_tag(
    request: TagCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Create/assign experiment tag to sessions."""
    count = await create_tag(
        db,
        request.tag_name,
        session_ids=request.session_ids or None,
        date_from=request.date_from,
        date_to=request.date_to,
        project_path=request.project_path,
    )
    return {"tag_name": request.tag_name, "sessions_tagged": count}


@router.delete("/experiments/tags/{tag_name}")
async def delete_experiment_tag(
    tag_name: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Delete an experiment tag."""
    count = await delete_tag(db, tag_name)
    if count == 0:
        raise HTTPException(status_code=404, detail=f"Tag '{tag_name}' not found")
    return {"tag_name": tag_name, "deleted_count": count}


@router.get("/experiments/compare", response_model=ComparisonResponse)
async def compare_experiment_tags(
    tag_a: str,
    tag_b: str,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Compare two experiment tags side by side."""
    result = await compare_tags(db, tag_a, tag_b)
    return result


@router.get("/experiments/compare-multi")
async def compare_multi_tags(
    tags: str = Query(..., description="Comma-separated tag names (2-4)"),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Compare 2-4 experiment tags across metrics."""
    tag_list = [t.strip() for t in tags.split(",") if t.strip()]
    if len(tag_list) < 2 or len(tag_list) > 4:
        raise HTTPException(status_code=400, detail="Provide 2-4 comma-separated tag names")
    data = await compare_tags_multi(db, tag_list, date_from, date_to)
    return {"tags": data}


@router.get("/experiments/tags/{tag_name}/sessions")
async def tag_sessions(
    tag_name: str,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get sessions belonging to a specific tag."""
    data = await get_tag_sessions(db, tag_name, date_from, date_to)
    return {"sessions": data}
