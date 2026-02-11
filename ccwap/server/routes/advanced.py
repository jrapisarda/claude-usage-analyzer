"""Advanced dashboard API endpoints."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.advanced import (
    ReliabilityResponse,
    ReliabilitySummary,
    ReliabilityHeatmapCell,
    ParetoItem,
    FailingWorkflow,
    BranchHealthResponse,
    BranchSummary,
    BranchTrendPoint,
    BranchAnomaly,
    PromptEfficiencyResponse,
    PromptEfficiencySummary,
    PromptEfficiencyScatterPoint,
    WorkflowBottleneckResponse,
    WorkflowTransition,
    RetryLoop,
    FailureHandoff,
    BlockedSession,
)
from ccwap.server.queries.advanced_queries import (
    get_reliability_dashboard,
    get_branch_health_dashboard,
    get_prompt_efficiency_dashboard,
    get_workflow_bottlenecks_dashboard,
)

router = APIRouter(prefix="/api", tags=["advanced"])


@router.get("/reliability", response_model=ReliabilityResponse)
async def reliability_dashboard(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    data = await get_reliability_dashboard(db, date_from, date_to)
    return ReliabilityResponse(
        summary=ReliabilitySummary(**data["summary"]),
        heatmap=[ReliabilityHeatmapCell(**r) for r in data["heatmap"]],
        pareto_tools=[ParetoItem(**r) for r in data["pareto_tools"]],
        pareto_commands=[ParetoItem(**r) for r in data["pareto_commands"]],
        pareto_languages=[ParetoItem(**r) for r in data["pareto_languages"]],
        by_branch=data["by_branch"],
        top_failing_workflows=[FailingWorkflow(**r) for r in data["top_failing_workflows"]],
    )


@router.get("/branch-health", response_model=BranchHealthResponse)
async def branch_health_dashboard(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    branches: Optional[str] = Query(None, description="Comma-separated branch filters"),
    db: aiosqlite.Connection = Depends(get_db),
):
    data = await get_branch_health_dashboard(db, date_from, date_to, branches)
    return BranchHealthResponse(
        branches=[BranchSummary(**r) for r in data["branches"]],
        trend=[BranchTrendPoint(**r) for r in data["trend"]],
        anomalies=[BranchAnomaly(**r) for r in data["anomalies"]],
    )


@router.get("/prompt-efficiency", response_model=PromptEfficiencyResponse)
async def prompt_efficiency_dashboard(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    data = await get_prompt_efficiency_dashboard(db, date_from, date_to)
    return PromptEfficiencyResponse(
        summary=PromptEfficiencySummary(**data["summary"]),
        funnel=data["funnel"],
        by_stop_reason=data["by_stop_reason"],
        scatter=[PromptEfficiencyScatterPoint(**r) for r in data["scatter"]],
        outliers=[PromptEfficiencyScatterPoint(**r) for r in data["outliers"]],
    )


@router.get("/workflow-bottlenecks", response_model=WorkflowBottleneckResponse)
async def workflow_bottlenecks_dashboard(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    data = await get_workflow_bottlenecks_dashboard(db, date_from, date_to)
    return WorkflowBottleneckResponse(
        transition_matrix=[WorkflowTransition(**r) for r in data["transition_matrix"]],
        retry_loops=[RetryLoop(**r) for r in data["retry_loops"]],
        failure_handoffs=[FailureHandoff(**r) for r in data["failure_handoffs"]],
        blocked_sessions=[BlockedSession(**r) for r in data["blocked_sessions"]],
    )

