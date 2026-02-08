"""Heatmap API endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.heatmap import HeatmapResponse, HeatmapCell
from ccwap.server.queries.heatmap_queries import get_heatmap_data

router = APIRouter(prefix="/api", tags=["heatmap"])


@router.get("/heatmap", response_model=HeatmapResponse)
async def heatmap(
    metric: str = Query("sessions", pattern="^(sessions|cost|loc|tool_calls)$"),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get heatmap data grouped by day-of-week and hour."""
    cells_data, max_value = await get_heatmap_data(db, date_from, date_to, metric)
    cells = [HeatmapCell(**c) for c in cells_data]
    return HeatmapResponse(cells=cells, metric=metric, max_value=max_value)
