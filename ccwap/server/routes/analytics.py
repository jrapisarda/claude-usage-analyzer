"""Deep analytics API endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.analytics import AnalyticsResponse
from ccwap.server.queries.analytics_queries import (
    get_thinking_analysis,
    get_truncation_analysis,
    get_sidechain_analysis,
    get_cache_tier_analysis,
    get_branch_analytics,
    get_version_impact,
    get_skills_agents,
)

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/analytics", response_model=AnalyticsResponse)
async def analytics(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get complete deep analytics data."""
    thinking = await get_thinking_analysis(db, date_from, date_to)
    truncation = await get_truncation_analysis(db, date_from, date_to)
    sidechains = await get_sidechain_analysis(db, date_from, date_to)
    cache_tiers = await get_cache_tier_analysis(db, date_from, date_to)
    branches = await get_branch_analytics(db, date_from, date_to)
    versions = await get_version_impact(db, date_from, date_to)
    skills_agents = await get_skills_agents(db, date_from, date_to)

    return AnalyticsResponse(
        thinking=thinking,
        truncation=truncation,
        sidechains=sidechains,
        cache_tiers=cache_tiers,
        branches=branches,
        versions=versions,
        skills_agents=skills_agents,
    )


@router.get("/analytics/thinking-trend")
async def thinking_trend(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get daily thinking chars by model for trend chart."""
    from ccwap.server.queries.analytics_queries import get_thinking_trend
    data = await get_thinking_trend(db, date_from, date_to)
    return data


@router.get("/analytics/cache-trend")
async def cache_trend(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get daily cache tier breakdown for trend chart."""
    from ccwap.server.queries.analytics_queries import get_cache_trend
    data = await get_cache_trend(db, date_from, date_to)
    return data
