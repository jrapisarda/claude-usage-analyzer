"""Productivity API endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.productivity import ProductivityResponse
from ccwap.server.queries.productivity_queries import (
    get_efficiency_summary,
    get_loc_trend,
    get_language_breakdown,
    get_tool_usage,
    get_error_analysis,
    get_file_hotspots,
    get_efficiency_trend,
    get_language_trend,
    get_tool_success_trend,
    get_file_churn,
)

router = APIRouter(prefix="/api", tags=["productivity"])


@router.get("/productivity", response_model=ProductivityResponse)
async def productivity(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get complete productivity analysis."""
    summary = await get_efficiency_summary(db, date_from, date_to)
    loc_trend = await get_loc_trend(db, date_from, date_to)
    languages = await get_language_breakdown(db, date_from, date_to)
    tool_usage = await get_tool_usage(db, date_from, date_to)
    error_analysis = await get_error_analysis(db, date_from, date_to)
    file_hotspots = await get_file_hotspots(db, date_from, date_to)

    return ProductivityResponse(
        summary=summary,
        loc_trend=loc_trend,
        languages=languages,
        tool_usage=tool_usage,
        error_analysis=error_analysis,
        file_hotspots=file_hotspots,
    )


@router.get("/productivity/efficiency-trend")
async def efficiency_trend(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get daily cost per kLOC trend."""
    data = await get_efficiency_trend(db, date_from, date_to)
    return data


@router.get("/productivity/language-trend")
async def language_trend(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get daily LOC by language."""
    data = await get_language_trend(db, date_from, date_to)
    return data


@router.get("/productivity/tool-success-trend")
async def tool_success_trend(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get daily success rate per tool."""
    data = await get_tool_success_trend(db, date_from, date_to)
    return data


@router.get("/productivity/file-churn")
async def file_churn(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    limit: int = Query(50),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get top files by edit count."""
    data = await get_file_churn(db, date_from, date_to, limit=limit)
    return data
