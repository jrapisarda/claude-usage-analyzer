"""Model comparison API endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.model_comparison import (
    ModelComparisonResponse,
    ModelMetrics,
    ModelUsageTrend,
    ModelScatterPoint,
)
from ccwap.server.queries.model_queries import (
    get_model_metrics,
    get_model_usage_trend,
    get_model_scatter,
)

router = APIRouter(prefix="/api", tags=["models"])


@router.get("/models", response_model=ModelComparisonResponse)
async def model_comparison(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get model comparison data with metrics, trends, and scatter plot."""
    metrics = await get_model_metrics(db, date_from, date_to)
    usage_trend = await get_model_usage_trend(db, date_from, date_to)
    scatter = await get_model_scatter(db, date_from, date_to)
    return ModelComparisonResponse(
        models=[ModelMetrics(**m) for m in metrics],
        usage_trend=[ModelUsageTrend(**u) for u in usage_trend],
        scatter=[ModelScatterPoint(**s) for s in scatter],
    )
