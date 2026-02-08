"""Pydantic models for deep analytics API."""

from typing import List, Optional, Dict
from pydantic import BaseModel


class ThinkingAnalysis(BaseModel):
    """Extended thinking analysis."""
    total_thinking_chars: int = 0
    avg_thinking_per_turn: float = 0.0
    turns_with_thinking: int = 0
    total_turns: int = 0
    thinking_rate: float = 0.0
    by_model: List[Dict] = []


class TruncationAnalysis(BaseModel):
    """Truncation/stop reason breakdown."""
    total_turns: int = 0
    by_stop_reason: List[Dict] = []


class SidechainAnalysis(BaseModel):
    """Sidechain/branching analysis."""
    total_sidechains: int = 0
    sidechain_rate: float = 0.0
    by_project: List[Dict] = []


class CacheTierAnalysis(BaseModel):
    """Ephemeral cache tier analysis."""
    ephemeral_5m_tokens: int = 0
    ephemeral_1h_tokens: int = 0
    standard_cache_tokens: int = 0
    by_date: List[Dict] = []


class BranchAnalytics(BaseModel):
    """Branch-aware analytics."""
    branches: List[Dict] = []


class VersionImpact(BaseModel):
    """CC version impact analysis."""
    versions: List[Dict] = []


class SkillsAgents(BaseModel):
    """Skills and agents analysis."""
    total_agent_spawns: int = 0
    total_skill_invocations: int = 0
    agent_cost: float = 0.0
    by_date: List[Dict] = []


class AnalyticsResponse(BaseModel):
    """Complete deep analytics data."""
    thinking: ThinkingAnalysis
    truncation: TruncationAnalysis
    sidechains: SidechainAnalysis
    cache_tiers: CacheTierAnalysis
    branches: BranchAnalytics
    versions: VersionImpact
    skills_agents: SkillsAgents
