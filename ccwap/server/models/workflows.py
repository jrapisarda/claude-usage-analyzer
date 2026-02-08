"""Pydantic models for workflows API."""

from typing import List

from pydantic import BaseModel


class UserTypeBreakdown(BaseModel):
    user_type: str
    sessions: int
    total_cost: float
    total_turns: int


class AgentTreeNode(BaseModel):
    session_id: str
    project_display: str
    user_type: str
    total_cost: float
    children: List['AgentTreeNode'] = []


class ToolSequence(BaseModel):
    sequence: List[str]
    count: int
    pct: float


class UserTypeTrend(BaseModel):
    date: str
    user_type: str
    sessions: int
    cost: float


class WorkflowResponse(BaseModel):
    user_types: List[UserTypeBreakdown]
    user_type_trend: List[UserTypeTrend]
    agent_trees: List[AgentTreeNode]
    tool_sequences: List[ToolSequence]
