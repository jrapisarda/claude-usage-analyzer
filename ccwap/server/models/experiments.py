"""Pydantic models for experiments API."""

from typing import List, Optional, Dict
from pydantic import BaseModel


class ExperimentTag(BaseModel):
    """An experiment tag."""
    tag_name: str
    session_count: int = 0
    created_at: Optional[str] = None


class TagCreateRequest(BaseModel):
    """Request to create/assign tags."""
    tag_name: str
    session_ids: List[str] = []
    date_from: Optional[str] = None
    date_to: Optional[str] = None
    project_path: Optional[str] = None


class TagDeleteRequest(BaseModel):
    """Request to delete a tag."""
    tag_name: str


class ComparisonMetric(BaseModel):
    """A single comparison metric between two tags."""
    metric_name: str
    tag_a_value: float = 0.0
    tag_b_value: float = 0.0
    absolute_delta: float = 0.0
    percentage_delta: float = 0.0
    is_improvement: bool = True


class ComparisonResponse(BaseModel):
    """Tag comparison results."""
    tag_a: str
    tag_b: str
    tag_a_sessions: int = 0
    tag_b_sessions: int = 0
    metrics: List[ComparisonMetric] = []


class TagListResponse(BaseModel):
    """List of experiment tags."""
    tags: List[ExperimentTag]
