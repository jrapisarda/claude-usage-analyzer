"""Pydantic models for the sessions API."""

from typing import List, Optional, Dict
from pydantic import BaseModel

from ccwap.server.models.common import PaginationMeta


class SessionListItem(BaseModel):
    """Session in the list view."""
    session_id: str
    project_path: str
    project_display: Optional[str] = None
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    duration_seconds: int = 0
    cost: float = 0.0
    turns: int = 0
    user_turns: int = 0
    tool_calls: int = 0
    errors: int = 0
    is_agent: bool = False
    cc_version: Optional[str] = None
    git_branch: Optional[str] = None
    model: Optional[str] = None


class SessionsResponse(BaseModel):
    """Paginated session list."""
    sessions: List[SessionListItem]
    pagination: PaginationMeta


class ToolCallDetail(BaseModel):
    """Tool call within a session replay turn."""
    tool_name: str
    file_path: Optional[str] = None
    success: bool = True
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    loc_written: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    language: Optional[str] = None


class ReplayTurn(BaseModel):
    """A single turn in the session replay timeline."""
    uuid: str
    timestamp: Optional[str] = None
    entry_type: str
    model: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    thinking_chars: int = 0
    cost: float = 0.0
    cumulative_cost: float = 0.0
    stop_reason: Optional[str] = None
    is_sidechain: bool = False
    is_meta: bool = False
    user_prompt_preview: Optional[str] = None
    tool_calls: List[ToolCallDetail] = []


class SessionReplayResponse(BaseModel):
    """Full session replay data."""
    session_id: str
    project_path: str
    project_display: Optional[str] = None
    first_timestamp: Optional[str] = None
    last_timestamp: Optional[str] = None
    duration_seconds: int = 0
    cc_version: Optional[str] = None
    git_branch: Optional[str] = None
    is_agent: bool = False
    total_cost: float = 0.0
    total_turns: int = 0
    total_user_turns: int = 0
    total_tool_calls: int = 0
    total_errors: int = 0
    cost_by_model: Dict[str, float] = {}
    tool_distribution: Dict[str, int] = {}
    turns: List[ReplayTurn] = []
