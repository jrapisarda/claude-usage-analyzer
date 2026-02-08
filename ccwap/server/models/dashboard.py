"""Pydantic models for the dashboard API."""

from typing import List, Optional
from pydantic import BaseModel


class VitalsData(BaseModel):
    """Today's key metrics."""
    sessions: int = 0
    cost: float = 0.0
    loc_written: int = 0
    error_rate: float = 0.0
    user_turns: int = 0
    messages: int = 0
    input_tokens: int = 0
    output_tokens: int = 0


class SparklinePoint(BaseModel):
    """A single data point for sparkline charts."""
    date: str
    value: float


class TopProject(BaseModel):
    """Project summary for the dashboard grid."""
    project_path: str
    project_display: str
    sessions: int = 0
    cost: float = 0.0
    loc_written: int = 0
    error_rate: float = 0.0
    last_session: Optional[str] = None


class RecentSession(BaseModel):
    """Recent session for the activity feed."""
    session_id: str
    project_display: Optional[str] = None
    first_timestamp: Optional[str] = None
    duration_seconds: int = 0
    cost: float = 0.0
    turns: int = 0
    model: Optional[str] = None
    is_agent: bool = False


class CostTrendPoint(BaseModel):
    """A single data point for cost trend charts."""
    date: str
    cost: float = 0.0
    sessions: int = 0
    messages: int = 0


class DashboardResponse(BaseModel):
    """Complete dashboard data."""
    vitals: VitalsData
    sparkline_7d: List[SparklinePoint]
    top_projects: List[TopProject]
    cost_trend: List[CostTrendPoint]
    recent_sessions: List[RecentSession]
