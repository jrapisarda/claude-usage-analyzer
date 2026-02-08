"""Pydantic models for the projects API."""

from typing import List, Optional, Set
from pydantic import BaseModel

from ccwap.server.models.common import PaginationMeta


class ProjectDetail(BaseModel):
    """Full project metrics."""
    project_path: str
    project_display: str
    sessions: int = 0
    messages: int = 0
    user_turns: int = 0
    loc_written: int = 0
    loc_delivered: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    files_created: int = 0
    files_edited: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    thinking_chars: int = 0
    cost: float = 0.0
    cost_per_kloc: float = 0.0
    tokens_per_loc: float = 0.0
    error_count: int = 0
    error_rate: float = 0.0
    tool_calls: int = 0
    agent_spawns: int = 0
    duration_seconds: int = 0
    cache_hit_rate: float = 0.0
    avg_turn_cost: float = 0.0


class ProjectsResponse(BaseModel):
    """Paginated project list."""
    projects: List[ProjectDetail]
    pagination: PaginationMeta
    totals: Optional[ProjectDetail] = None
