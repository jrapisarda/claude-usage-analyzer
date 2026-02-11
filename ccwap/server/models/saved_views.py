"""Pydantic models for saved views and alert rules."""

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class SavedViewCreateRequest(BaseModel):
    name: str
    page: str
    filters: Dict[str, Any] = Field(default_factory=dict)


class SavedView(BaseModel):
    id: int
    name: str
    page: str
    filters: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None


class SavedViewsResponse(BaseModel):
    views: List[SavedView] = Field(default_factory=list)


class AlertRuleCreateRequest(BaseModel):
    name: str
    page: str
    metric: str
    operator: str
    threshold: float
    filters: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True


class AlertRule(BaseModel):
    id: int
    name: str
    page: str
    metric: str
    operator: str
    threshold: float
    filters: Dict[str, Any] = Field(default_factory=dict)
    enabled: bool = True
    created_at: Optional[str] = None


class AlertRuleEvaluation(BaseModel):
    rule_id: int
    name: str
    page: str
    metric: str
    operator: str
    threshold: float
    current_value: float
    triggered: bool


class AlertRulesResponse(BaseModel):
    rules: List[AlertRule] = Field(default_factory=list)


class AlertEvaluationResponse(BaseModel):
    evaluations: List[AlertRuleEvaluation] = Field(default_factory=list)
