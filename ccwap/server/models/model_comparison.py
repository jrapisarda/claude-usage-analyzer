"""Pydantic models for model comparison API."""

from typing import List

from pydantic import BaseModel


class ModelMetrics(BaseModel):
    model: str
    sessions: int
    turns: int
    total_cost: float
    avg_turn_cost: float
    total_input_tokens: int
    total_output_tokens: int
    avg_thinking_chars: float
    loc_written: int


class ModelUsageTrend(BaseModel):
    date: str
    model: str
    count: int


class ModelScatterPoint(BaseModel):
    session_id: str
    model: str
    cost: float
    loc_written: int


class ModelComparisonResponse(BaseModel):
    models: List[ModelMetrics]
    usage_trend: List[ModelUsageTrend]
    scatter: List[ModelScatterPoint]
