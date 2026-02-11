"""Analytics explorer API endpoints."""

import math
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException

import aiosqlite

from ccwap.server.dependencies import get_db, get_config
from ccwap.server.models.common import PaginationMeta
from ccwap.server.models.explorer import (
    ExplorerResponse,
    ExplorerRow,
    ExplorerMetadata,
    ExplorerFiltersResponse,
    FilterOption,
    ExplorerDrilldownResponse,
    ExplorerDrilldownBucket,
    ExplorerDrilldownSession,
    get_allowed_dimensions,
    TURNS_METRICS,
    TOOL_METRICS,
    SESSION_METRICS,
)
from ccwap.server.queries.explorer_queries import (
    query_explorer,
    query_explorer_drilldown,
    get_filter_options,
)
from ccwap.server.queries.materialized_queries import is_materialized_enabled

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
    config: dict = Depends(get_config),
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
        use_materialized=is_materialized_enabled(config),
    )

    return ExplorerResponse(
        rows=[ExplorerRow(**r) for r in rows],
        metadata=ExplorerMetadata(**metadata),
    )


@router.get("/explorer/drilldown", response_model=ExplorerDrilldownResponse)
async def explorer_drilldown(
    metric: str = Query(..., description="Metric to aggregate"),
    group_by: str = Query(..., description="Primary dimension used in explorer query"),
    group_value: str = Query(..., description="Selected group bucket value"),
    split_by: Optional[str] = Query(None, description="Secondary dimension used in explorer query"),
    split_value: Optional[str] = Query(None, description="Selected split bucket value"),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    projects: Optional[str] = Query(None, description="Comma-separated project filter"),
    models: Optional[str] = Query(None, description="Comma-separated model filter"),
    branches: Optional[str] = Query(None, description="Comma-separated branch filter"),
    languages: Optional[str] = Query(None, description="Comma-separated language filter"),
    page: int = Query(1, ge=1),
    limit: int = Query(25, ge=1, le=200),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get paginated session-level detail for a selected explorer bucket."""
    if metric not in ALL_METRICS:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid metric '{metric}'. Must be one of: {sorted(ALL_METRICS)}",
        )

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
        raise HTTPException(status_code=400, detail="split_by must differ from group_by")
    if split_by and not split_value:
        raise HTTPException(status_code=400, detail="split_value is required when split_by is set")
    if split_value and not split_by:
        raise HTTPException(status_code=400, detail="split_value requires split_by")

    sessions, total_count = await query_explorer_drilldown(
        db,
        metric=metric,
        group_by=group_by,
        group_value=group_value,
        split_by=split_by,
        split_value=split_value,
        date_from=date_from,
        date_to=date_to,
        projects=_parse_csv(projects),
        models=_parse_csv(models),
        branches=_parse_csv(branches),
        languages=_parse_csv(languages),
        page=page,
        limit=limit,
    )

    return ExplorerDrilldownResponse(
        bucket=ExplorerDrilldownBucket(
            metric=metric,
            group_by=group_by,
            group_value=group_value,
            split_by=split_by,
            split_value=split_value,
        ),
        sessions=[ExplorerDrilldownSession(**s) for s in sessions],
        pagination=PaginationMeta(
            page=page,
            limit=limit,
            total_count=total_count,
            total_pages=math.ceil(total_count / limit) if limit > 0 else 0,
        ),
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
