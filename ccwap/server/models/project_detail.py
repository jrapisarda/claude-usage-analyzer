"""Pydantic models for project detail API."""

from typing import List, Optional

from pydantic import BaseModel


class ProjectCostTrend(BaseModel):
    date: str
    cost: float


class ProjectLanguage(BaseModel):
    language: str
    loc_written: int


class ProjectTool(BaseModel):
    tool_name: str
    count: int
    success_rate: float


class ProjectBranch(BaseModel):
    branch: str
    sessions: int
    cost: float


class ProjectSession(BaseModel):
    session_id: str
    start_time: str
    total_cost: float
    turn_count: int
    loc_written: int
    model_default: Optional[str] = None


class ProjectDetailResponse(BaseModel):
    project_display: str
    total_cost: float
    total_sessions: int
    total_loc: int
    cost_trend: List[ProjectCostTrend]
    languages: List[ProjectLanguage]
    tools: List[ProjectTool]
    branches: List[ProjectBranch]
    sessions: List[ProjectSession]
