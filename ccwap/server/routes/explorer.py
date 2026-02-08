"""Analytics explorer API endpoints."""

from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.explorer import (
    ExplorerResponse,
    ExplorerRow,
    ExplorerMetadata,
    ExplorerFiltersResponse,
    FilterOption,
    get_allowed_dimensions,
    TURNS_METRICS,
    TOOL_METRICS,
    SESSION_METRICS,
)
from ccwap.server.queries.explorer_queries import (
    query_explorer,
    get_filter_options,
)

router = APIRouter(prefix="/api", tags=["explorer"])

ALL_METRICS = TURNS_METRICS | TOOL_METRICS | SESSION_METRICS


def _parse_csv(value: Optional[str]) -> Optional[List[str]]:
    """Parse comma-separated string into list, or None if empty."""
    if not value:
        return None
    items = [v.strip() for v in value.split(",") if v.strip()]
    return items if items else None


@router.get("/explorer", response_model=ExplorerResponse)
async def explorer(
    metric: str = Query(..., description="Metric to aggregate"),
    group_by: str = Query(..., description="Primary dimension to group by"),
    split_by: Optional[str] = Query(None, description="Secondary dimension to split by"),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    projects: Optional[str] = Query(None, description="Comma-separated project filter"),
    models: Optional[str] = Query(None, description="Comma-separated model filter"),
    branches: Optional[str] = Query(None, description="Comma-separated branch filter"),
    languages: Optional[str] = Query(None, description="Comma-separated language filter"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Flexible explorer query endpoint."""
    # Validate metric
    if metric not in ALL_METRICS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric '{metric}'. Must be one of: {sorted(ALL_METRICS)}",
        )

    # Validate dimensions
    allowed = get_allowed_dimensions(metric)
    if group_by not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Dimension '{group_by}' not available for metric '{metric}'. Allowed: {sorted(allowed)}",
        )
    if split_by and split_by not in allowed:
        raise HTTPException(
            status_code=400,
            detail=f"Split dimension '{split_by}' not available for metric '{metric}'. Allowed: {sorted(allowed)}",
        )
    if split_by and split_by == group_by:
        raise HTTPException(
            status_code=400,
            detail="split_by must differ from group_by",
        )

    rows, metadata = await query_explorer(
        db,
        metric=metric,
        group_by=group_by,
        split_by=split_by,
        date_from=date_from,
        date_to=date_to,
        projects=_parse_csv(projects),
        models=_parse_csv(models),
        branches=_parse_csv(branches),
        languages=_parse_csv(languages),
    )

    return ExplorerResponse(
        rows=[ExplorerRow(**r) for r in rows],
        metadata=ExplorerMetadata(**metadata),
    )


@router.get("/explorer/filters", response_model=ExplorerFiltersResponse)
async def explorer_filters(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get available filter values for dropdowns."""
    data = await get_filter_options(db, date_from, date_to)

    return ExplorerFiltersResponse(
        projects=[FilterOption(**p) for p in data["projects"]],
        models=[FilterOption(**m) for m in data["models"]],
        branches=[FilterOption(**b) for b in data["branches"]],
        languages=[FilterOption(**l) for l in data["languages"]],
    )
