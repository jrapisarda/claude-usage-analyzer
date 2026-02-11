"""Saved views and alert rules API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.saved_views import (
    SavedViewCreateRequest,
    SavedView,
    SavedViewsResponse,
    AlertRuleCreateRequest,
    AlertRule,
    AlertRulesResponse,
    AlertEvaluationResponse,
    AlertRuleEvaluation,
)
from ccwap.server.queries.saved_views_queries import (
    create_saved_view,
    delete_saved_view,
    list_saved_views,
    create_alert_rule,
    delete_alert_rule,
    list_alert_rules,
    evaluate_alert_rules,
)

router = APIRouter(prefix="/api", tags=["saved_views"])


@router.get("/saved-views", response_model=SavedViewsResponse)
async def get_saved_views(
    page: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
):
    views = await list_saved_views(db, page=page)
    return SavedViewsResponse(views=[SavedView(**v) for v in views])


@router.post("/saved-views", response_model=SavedView)
async def create_saved_view_endpoint(
    request: SavedViewCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    view = await create_saved_view(
        db,
        name=request.name,
        page=request.page,
        filters=request.filters,
    )
    return SavedView(**view)


@router.delete("/saved-views/{view_id}")
async def delete_saved_view_endpoint(
    view_id: int,
    db: aiosqlite.Connection = Depends(get_db),
):
    deleted = await delete_saved_view(db, view_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Saved view not found")
    return {"deleted": deleted}


@router.get("/alert-rules", response_model=AlertRulesResponse)
async def get_alert_rules(
    page: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
):
    rules = await list_alert_rules(db, page=page)
    return AlertRulesResponse(rules=[AlertRule(**r) for r in rules])


@router.post("/alert-rules", response_model=AlertRule)
async def create_alert_rule_endpoint(
    request: AlertRuleCreateRequest,
    db: aiosqlite.Connection = Depends(get_db),
):
    try:
        rule = await create_alert_rule(
            db,
            name=request.name,
            page=request.page,
            metric=request.metric,
            operator=request.operator,
            threshold=request.threshold,
            filters=request.filters,
            enabled=request.enabled,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return AlertRule(**rule)


@router.delete("/alert-rules/{rule_id}")
async def delete_alert_rule_endpoint(
    rule_id: int,
    db: aiosqlite.Connection = Depends(get_db),
):
    deleted = await delete_alert_rule(db, rule_id)
    if deleted == 0:
        raise HTTPException(status_code=404, detail="Alert rule not found")
    return {"deleted": deleted}


@router.get("/alert-rules/evaluate", response_model=AlertEvaluationResponse)
async def evaluate_alert_rules_endpoint(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    page: Optional[str] = Query(None),
    db: aiosqlite.Connection = Depends(get_db),
):
    evaluations = await evaluate_alert_rules(db, date_from=date_from, date_to=date_to, page=page)
    return AlertEvaluationResponse(evaluations=[AlertRuleEvaluation(**e) for e in evaluations])

