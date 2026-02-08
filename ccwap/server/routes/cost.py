"""Cost analysis API endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.cost import CostAnalysisResponse
from ccwap.server.queries.cost_queries import (
    get_cost_summary,
    get_cost_by_token_type,
    get_cost_by_model,
    get_cost_trend,
    get_cost_by_project,
    get_cache_savings,
    get_spend_forecast,
    get_cost_anomalies,
    get_cumulative_cost,
    get_cache_simulation,
)

router = APIRouter(prefix="/api", tags=["cost"])


@router.get("/cost", response_model=CostAnalysisResponse)
async def cost_analysis(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get complete cost analysis data."""
    summary = await get_cost_summary(db, date_from, date_to)
    by_token_type = await get_cost_by_token_type(db, date_from, date_to)
    by_model = await get_cost_by_model(db, date_from, date_to)
    trend = await get_cost_trend(db, date_from, date_to)
    by_project = await get_cost_by_project(db, date_from, date_to)
    cache_savings = await get_cache_savings(db, date_from, date_to)
    forecast = await get_spend_forecast(db)

    return CostAnalysisResponse(
        summary=summary,
        by_token_type=by_token_type,
        by_model=by_model,
        trend=trend,
        by_project=by_project,
        cache_savings=cache_savings,
        forecast=forecast,
    )


@router.get("/cost/anomalies")
async def cost_anomalies(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get daily cost with anomaly detection via IQR method."""
    data = await get_cost_anomalies(db, date_from, date_to)
    return data


@router.get("/cost/cumulative")
async def cost_cumulative(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get running sum of daily cost."""
    data = await get_cumulative_cost(db, date_from, date_to)
    return data


@router.get("/cost/cache-simulation")
async def cost_cache_simulation(
    target_hit_rate: float = Query(0.5),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """What-if simulation for cache hit rate improvement."""
    data = await get_cache_simulation(db, target_hit_rate, date_from, date_to)
    return data
