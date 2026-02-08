"""Dashboard API endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.dashboard import DashboardResponse
from ccwap.server.queries.dashboard_queries import (
    get_vitals_today,
    get_sparkline_7d,
    get_top_projects,
    get_cost_trend,
    get_recent_sessions,
)

router = APIRouter(prefix="/api", tags=["dashboard"])


@router.get("/dashboard", response_model=DashboardResponse)
async def dashboard(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get complete dashboard data."""
    vitals = await get_vitals_today(db, date_from, date_to)
    sparkline = await get_sparkline_7d(db, date_from, date_to)
    top_projects = await get_top_projects(db, date_from, date_to)
    cost_trend = await get_cost_trend(db, date_from, date_to)
    recent = await get_recent_sessions(db, date_from=date_from, date_to=date_to)

    return DashboardResponse(
        vitals=vitals,
        sparkline_7d=sparkline,
        top_projects=top_projects,
        cost_trend=cost_trend,
        recent_sessions=recent,
    )


@router.get("/dashboard/deltas")
async def dashboard_deltas(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get period-over-period delta metrics."""
    from ccwap.server.queries.dashboard_queries import get_period_deltas
    return await get_period_deltas(db, date_from, date_to)


@router.get("/dashboard/activity-calendar")
async def activity_calendar(
    days: int = Query(90, ge=7, le=365),
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get daily activity for calendar heatmap."""
    from ccwap.server.queries.dashboard_queries import get_activity_calendar
    return await get_activity_calendar(db, days)
