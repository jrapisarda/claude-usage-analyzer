"""
Data structures (entities) for CCWAP.

Uses dataclasses for clean, typed data structures.
Named 'entities' instead of 'dataclasses' to avoid stdlib import confusion.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional, Set, List


@dataclass
class TokenUsage:
    """Token usage breakdown for a single turn."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    ephemeral_5m_tokens: int = 0
    ephemeral_1h_tokens: int = 0

    @property
    def total_tokens(self) -> int:
        """Total tokens across all types."""
        return (
            self.input_tokens +
            self.output_tokens +
            self.cache_read_tokens +
            self.cache_write_tokens
        )


@dataclass
class TurnData:
    """Data for a single conversation turn (JSONL entry)."""
    uuid: str
    session_id: str
    timestamp: datetime
    entry_type: str  # 'user', 'assistant', 'queue-operation', etc.
    parent_uuid: Optional[str] = None
    model: Optional[str] = None
    usage: TokenUsage = field(default_factory=TokenUsage)
    cost: float = 0.0
    pricing_version: Optional[str] = None
    stop_reason: Optional[str] = None
    service_tier: Optional[str] = None
    is_sidechain: bool = False
    is_meta: bool = False
    source_tool_use_id: Optional[str] = None
    thinking_chars: int = 0
    user_type: Optional[str] = None
    user_prompt_preview: Optional[str] = None


@dataclass
class ToolCallData:
    """Data for a single tool call within a turn."""
    tool_use_id: str
    tool_name: str
    turn_id: Optional[int] = None
    session_id: Optional[str] = None
    file_path: Optional[str] = None
    input_size: int = 0
    output_size: int = 0
    success: bool = True
    error_message: Optional[str] = None
    error_category: Optional[str] = None
    command_name: Optional[str] = None
    loc_written: int = 0
    lines_added: int = 0
    lines_deleted: int = 0
    language: Optional[str] = None
    timestamp: Optional[datetime] = None


@dataclass
class SessionData:
    """Data for a complete session."""
    session_id: str
    project_path: str
    file_path: str
    first_timestamp: datetime
    last_timestamp: Optional[datetime] = None
    project_display: Optional[str] = None
    duration_seconds: int = 0
    cc_version: Optional[str] = None
    git_branch: Optional[str] = None
    cwd: Optional[str] = None
    is_agent: bool = False
    parent_session_id: Optional[str] = None
    file_mtime: float = 0.0
    file_size: int = 0
    turns: List[TurnData] = field(default_factory=list)
    tool_calls: List[ToolCallData] = field(default_factory=list)
    models_used: Set[str] = field(default_factory=set)


@dataclass
class ProjectStats:
    """
    All 30+ metrics per project.

    This is the comprehensive project-level statistics structure
    used for the --projects report.
    """
    project_path: str
    project_display: str

    # Session metrics
    sessions: int = 0
    messages: int = 0
    user_turns: int = 0

    # LOC metrics
    loc_written: int = 0  # LOC Generated (total Write content)
    loc_delivered: int = 0  # Net LOC (final file states)
    lines_added: int = 0
    lines_deleted: int = 0
    files_created: int = 0
    files_edited: int = 0

    # Token metrics
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0
    thinking_chars: int = 0

    # Cost metrics
    cost: float = 0.0
    cost_per_kloc: float = 0.0
    tokens_per_loc: float = 0.0

    # Error metrics
    error_count: int = 0
    error_rate: float = 0.0
    tool_calls: int = 0
    tool_success_rate: float = 0.0

    # Workflow metrics
    agent_spawns: int = 0
    skill_invocations: int = 0
    duration_seconds: int = 0

    # Metadata
    cc_version: Optional[str] = None
    git_branch: Optional[str] = None
    models_used: Set[str] = field(default_factory=set)

    # Derived metrics
    cache_hit_rate: float = 0.0
    avg_turn_cost: float = 0.0
    loc_per_session: float = 0.0
    errors_per_kloc: float = 0.0

    def calculate_derived_metrics(self) -> None:
        """Calculate derived metrics from raw data."""
        # Cost/KLOC
        if self.loc_written > 0:
            self.cost_per_kloc = self.cost / (self.loc_written / 1000)
            self.tokens_per_loc = self.output_tokens / self.loc_written

        # Error rate
        if self.tool_calls > 0:
            self.error_rate = self.error_count / self.tool_calls
            self.tool_success_rate = (self.tool_calls - self.error_count) / self.tool_calls

        # Cache hit rate
        total_input = self.input_tokens + self.cache_read_tokens
        if total_input > 0:
            self.cache_hit_rate = self.cache_read_tokens / total_input

        # Average turn cost
        if self.user_turns > 0:
            self.avg_turn_cost = self.cost / self.user_turns

        # LOC per session
        if self.sessions > 0:
            self.loc_per_session = self.loc_written / self.sessions

        # Errors per KLOC
        if self.loc_written > 0:
            self.errors_per_kloc = self.error_count / (self.loc_written / 1000)


@dataclass
class DailySummary:
    """Aggregated metrics for a single day."""
    date: str  # YYYY-MM-DD
    sessions: int = 0
    messages: int = 0
    user_turns: int = 0
    tool_calls: int = 0
    errors: int = 0
    error_rate: float = 0.0
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
    agent_spawns: int = 0
    skill_invocations: int = 0


@dataclass
class ComparisonResult:
    """Result of comparing two time periods or experiments."""
    metric_name: str
    previous_value: float
    current_value: float
    absolute_delta: float = 0.0
    percentage_delta: float = 0.0
    is_improvement: bool = True

    def calculate_deltas(self, lower_is_better: bool = False) -> None:
        """Calculate absolute and percentage deltas."""
        self.absolute_delta = self.current_value - self.previous_value

        if self.previous_value != 0:
            self.percentage_delta = (self.absolute_delta / self.previous_value) * 100
        elif self.current_value != 0:
            self.percentage_delta = float('inf')
        else:
            self.percentage_delta = 0.0

        # Determine if this is an improvement
        if lower_is_better:
            self.is_improvement = self.absolute_delta < 0
        else:
            self.is_improvement = self.absolute_delta > 0
