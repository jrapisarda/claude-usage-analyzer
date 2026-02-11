"""Pydantic models for advanced analytics dashboards."""

from typing import List, Optional, Dict, Any

from pydantic import BaseModel


class ReliabilitySummary(BaseModel):
    total_tool_calls: int = 0
    total_errors: int = 0
    error_rate: float = 0.0
    error_cost: float = 0.0


class ReliabilityHeatmapCell(BaseModel):
    tool_name: str
    error_category: str
    errors: int = 0
    error_cost: float = 0.0


class ParetoItem(BaseModel):
    label: str
    count: int = 0
    cost: float = 0.0


class FailingWorkflow(BaseModel):
    workflow: str
    from_tool: str
    to_tool: str
    branch: str
    failures: int = 0
    cost: float = 0.0


class ReliabilityResponse(BaseModel):
    summary: ReliabilitySummary
    heatmap: List[ReliabilityHeatmapCell] = []
    pareto_tools: List[ParetoItem] = []
    pareto_commands: List[ParetoItem] = []
    pareto_languages: List[ParetoItem] = []
    by_branch: List[Dict[str, Any]] = []
    top_failing_workflows: List[FailingWorkflow] = []


class BranchSummary(BaseModel):
    branch: str
    cost: float = 0.0
    errors: int = 0
    tool_calls: int = 0
    loc_written: int = 0
    cache_hit_rate: float = 0.0


class BranchTrendPoint(BaseModel):
    date: str
    branch: str
    cost: float = 0.0
    errors: int = 0
    tool_calls: int = 0
    loc_written: int = 0
    cache_hit_rate: float = 0.0


class BranchAnomaly(BaseModel):
    date: str
    branch: str
    cost: float = 0.0
    zscore: float = 0.0
    reason: str = "cost_spike"


class BranchHealthResponse(BaseModel):
    branches: List[BranchSummary] = []
    trend: List[BranchTrendPoint] = []
    anomalies: List[BranchAnomaly] = []


class PromptEfficiencySummary(BaseModel):
    total_sessions: int = 0
    sessions_with_thinking: int = 0
    sessions_with_truncation: int = 0
    high_cost_low_output_sessions: int = 0
    avg_cost_per_loc: float = 0.0


class PromptEfficiencyScatterPoint(BaseModel):
    session_id: str
    project: str
    model: str
    branch: str
    cost: float = 0.0
    thinking_chars: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    loc_written: int = 0
    truncations: int = 0
    token_mix_ratio: float = 0.0
    output_per_cost: float = 0.0
    efficiency_score: float = 0.0


class PromptEfficiencyResponse(BaseModel):
    summary: PromptEfficiencySummary
    funnel: List[Dict[str, Any]] = []
    by_stop_reason: List[Dict[str, Any]] = []
    scatter: List[PromptEfficiencyScatterPoint] = []
    outliers: List[PromptEfficiencyScatterPoint] = []


class WorkflowTransition(BaseModel):
    from_tool: str
    to_tool: str
    count: int = 0
    failures: int = 0
    failure_rate: float = 0.0


class RetryLoop(BaseModel):
    session_id: str
    tool_name: str
    retries: int = 0
    branch: str
    user_type: str


class FailureHandoff(BaseModel):
    parent_session_id: str
    child_session_id: str
    branch: str
    handoff: str
    errors: int = 0
    error_rate: float = 0.0


class BlockedSession(BaseModel):
    session_id: str
    project: str
    branch: str
    user_type: str
    failures: int = 0
    retries: int = 0
    stall_score: int = 0


class WorkflowBottleneckResponse(BaseModel):
    transition_matrix: List[WorkflowTransition] = []
    retry_loops: List[RetryLoop] = []
    failure_handoffs: List[FailureHandoff] = []
    blocked_sessions: List[BlockedSession] = []
