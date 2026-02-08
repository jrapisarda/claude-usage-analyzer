"""Pydantic models for cost analysis API."""

from typing import List, Optional, Dict
from pydantic import BaseModel


class CostSummary(BaseModel):
    """Cost summary cards."""
    total_cost: float = 0.0
    avg_daily_cost: float = 0.0
    cost_today: float = 0.0
    cost_this_week: float = 0.0
    cost_this_month: float = 0.0
    projected_monthly: float = 0.0


class CostByTokenType(BaseModel):
    """Cost breakdown by token type."""
    input_cost: float = 0.0
    output_cost: float = 0.0
    cache_read_cost: float = 0.0
    cache_write_cost: float = 0.0
    total_cost: float = 0.0


class CostByModel(BaseModel):
    """Cost for a specific model."""
    model: str
    cost: float = 0.0
    turns: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    percentage: float = 0.0


class CostTrendPoint(BaseModel):
    """A data point in the cost trend."""
    date: str
    cost: float = 0.0
    cumulative_cost: float = 0.0


class CostByProject(BaseModel):
    """Cost summary per project."""
    project_path: str
    project_display: str
    cost: float = 0.0
    percentage: float = 0.0


class CacheSavings(BaseModel):
    """Cache savings analysis."""
    total_cache_read_tokens: int = 0
    total_input_tokens: int = 0
    cache_hit_rate: float = 0.0
    estimated_savings: float = 0.0
    cost_without_cache: float = 0.0
    actual_cost: float = 0.0


class SpendForecast(BaseModel):
    """Spend forecast data."""
    daily_avg: float = 0.0
    projected_7d: float = 0.0
    projected_14d: float = 0.0
    projected_30d: float = 0.0
    trend_direction: str = "stable"
    confidence: float = 0.0


class CostAnalysisResponse(BaseModel):
    """Complete cost analysis data."""
    summary: CostSummary
    by_token_type: CostByTokenType
    by_model: List[CostByModel]
    trend: List[CostTrendPoint]
    by_project: List[CostByProject]
    cache_savings: CacheSavings
    forecast: SpendForecast
