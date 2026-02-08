"""Workflows API endpoint."""

from typing import Optional

from fastapi import APIRouter, Depends, Query

import aiosqlite

from ccwap.server.dependencies import get_db
from ccwap.server.models.workflows import (
    WorkflowResponse,
    UserTypeBreakdown,
    UserTypeTrend,
    AgentTreeNode,
    ToolSequence,
)
from ccwap.server.queries.workflow_queries import (
    get_user_type_breakdown,
    get_user_type_trend,
    get_agent_trees,
    get_tool_sequences,
)

router = APIRouter(prefix="/api", tags=["workflows"])


@router.get("/workflows", response_model=WorkflowResponse)
async def workflows(
    date_from: Optional[str] = Query(None, alias="from"),
    date_to: Optional[str] = Query(None, alias="to"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get workflow analytics including user types, agent trees, and tool sequences."""
    user_types = await get_user_type_breakdown(db, date_from, date_to)
    trend = await get_user_type_trend(db, date_from, date_to)
    trees = await get_agent_trees(db, date_from, date_to)
    sequences = await get_tool_sequences(db, date_from, date_to)
    return WorkflowResponse(
        user_types=[UserTypeBreakdown(**u) for u in user_types],
        user_type_trend=[UserTypeTrend(**t) for t in trend],
        agent_trees=[AgentTreeNode(**t) for t in trees],
        tool_sequences=[ToolSequence(**s) for s in sequences],
    )
