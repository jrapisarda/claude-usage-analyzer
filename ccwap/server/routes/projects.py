"""Projects API endpoint."""

import base64
import math
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.common import PaginationMeta
from ccwap.server.models.project_detail import ProjectDetailResponse
from ccwap.server.models.projects import ProjectsResponse
from ccwap.server.queries.project_detail_queries import get_project_detail
from ccwap.server.queries.project_queries import get_projects

router = APIRouter(prefix="/api", tags=["projects"])


@router.get("/projects", response_model=ProjectsResponse)
async def list_projects(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    sort: str = Query("cost"),
    order: str = Query("desc"),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    search: Optional[str] = None,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get paginated project list with full metrics."""
    projects, total_count = await get_projects(
        db, date_from, date_to, sort, order, page, limit, search
    )

    return ProjectsResponse(
        projects=projects,
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total_count=total_count,
            total_pages=math.ceil(total_count / limit) if limit > 0 else 0,
        ),
    )


@router.get("/projects/{encoded_path}/detail", response_model=ProjectDetailResponse)
async def project_detail(
    encoded_path: str,
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get detailed data for a specific project by base64url-encoded path."""
    # Base64url decode
    try:
        project_path = base64.urlsafe_b64decode(encoded_path + "==").decode("utf-8")
    except Exception:
        project_path = encoded_path

    result = await get_project_detail(db, project_path, date_from, date_to)
    if not result:
        raise HTTPException(status_code=404, detail="Project not found")
    return ProjectDetailResponse(**result)
