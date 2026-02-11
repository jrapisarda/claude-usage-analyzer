"""Pydantic models for analytics explorer API."""

from typing import List, Optional, Literal
from pydantic import BaseModel

from ccwap.server.models.common import PaginationMeta


MetricType = Literal[
    # Turns metrics
    "cost", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_write_tokens",
    "ephemeral_5m_tokens", "ephemeral_1h_tokens",
    "thinking_chars", "turns_count",
    # Tool metrics
    "loc_written", "tool_calls_count", "errors",
    "lines_added", "lines_deleted",
    # Session metrics
    "sessions_count", "duration_seconds",
]

DimensionType = Literal[
    "date", "model", "project", "branch", "language",
    "tool_name", "cc_version", "entry_type", "is_agent",
]

TURNS_METRICS: set = {
    "cost", "input_tokens", "output_tokens",
    "cache_read_tokens", "cache_write_tokens",
    "ephemeral_5m_tokens", "ephemeral_1h_tokens",
    "thinking_chars", "turns_count",
}

TOOL_METRICS: set = {
    "loc_written", "tool_calls_count", "errors",
    "lines_added", "lines_deleted",
}

SESSION_METRICS: set = {
    "sessions_count", "duration_seconds",
}

TURNS_DIMENSIONS: set = {
    "date", "model", "project", "branch",
    "cc_version", "entry_type", "is_agent",
}

TOOL_DIMENSIONS: set = {
    "date", "model", "project", "branch", "language",
    "tool_name", "cc_version", "entry_type", "is_agent",
}

SESSION_DIMENSIONS: set = {
    "date", "project", "branch", "cc_version", "is_agent",
}


def get_allowed_dimensions(metric: str) -> set:
    """Get allowed dimensions for a given metric."""
    if metric in TURNS_METRICS:
        return TURNS_DIMENSIONS
    if metric in TOOL_METRICS:
        return TOOL_DIMENSIONS
    if metric in SESSION_METRICS:
        return SESSION_DIMENSIONS
    return set()


class ExplorerRow(BaseModel):
    """Single data row from explorer query."""
    group: str
    split: Optional[str] = None
    value: float = 0.0


class ExplorerMetadata(BaseModel):
    """Metadata about the explorer query result."""
    metric: str
    group_by: str
    split_by: Optional[str] = None
    total: float = 0.0
    row_count: int = 0
    groups: List[str] = []
    splits: List[str] = []


class ExplorerResponse(BaseModel):
    """Complete explorer query response."""
    rows: List[ExplorerRow] = []
    metadata: ExplorerMetadata


class FilterOption(BaseModel):
    """Single filter option with count."""
    value: str
    label: str
    count: int = 0


class ExplorerFiltersResponse(BaseModel):
    """Available filter options."""
    projects: List[FilterOption] = []
    models: List[FilterOption] = []
    branches: List[FilterOption] = []
    languages: List[FilterOption] = []


class ExplorerDrilldownSession(BaseModel):
    """Session-level detail for a selected explorer bucket."""
    session_id: str
    project: str
    first_timestamp: Optional[str] = None
    user_type: str
    branch: str
    cc_version: str
    bucket_value: float = 0.0
    total_cost: float = 0.0
    turns: int = 0
    tool_calls: int = 0
    errors: int = 0


class ExplorerDrilldownBucket(BaseModel):
    """Selected explorer bucket context."""
    metric: str
    group_by: str
    group_value: str
    split_by: Optional[str] = None
    split_value: Optional[str] = None


class ExplorerDrilldownResponse(BaseModel):
    """Explorer drill-down response with paginated sessions."""
    bucket: ExplorerDrilldownBucket
    sessions: List[ExplorerDrilldownSession] = []
    pagination: PaginationMeta
