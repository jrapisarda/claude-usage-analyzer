"""Pydantic models for productivity API."""

from typing import List, Optional, Dict
from pydantic import BaseModel


class EfficiencySummary(BaseModel):
    """Efficiency summary cards."""
    total_loc_written: int = 0
    total_loc_delivered: int = 0
    avg_loc_per_session: float = 0.0
    cost_per_kloc: float = 0.0
    tokens_per_loc: float = 0.0
    error_rate: float = 0.0


class LocTrendPoint(BaseModel):
    """LOC trend data point."""
    date: str
    loc_written: int = 0
    loc_delivered: int = 0
    lines_added: int = 0
    lines_deleted: int = 0


class LanguageBreakdown(BaseModel):
    """LOC by language."""
    language: str
    loc_written: int = 0
    files_count: int = 0
    percentage: float = 0.0


class ToolUsageStat(BaseModel):
    """Tool usage statistics."""
    tool_name: str
    total_calls: int = 0
    success_count: int = 0
    error_count: int = 0
    success_rate: float = 0.0
    loc_written: int = 0


class ErrorCategory(BaseModel):
    """Error category breakdown."""
    category: str
    count: int = 0
    percentage: float = 0.0


class ErrorAnalysis(BaseModel):
    """Error analysis panel data."""
    total_errors: int = 0
    error_rate: float = 0.0
    categories: List[ErrorCategory] = []
    top_errors: List[Dict] = []


class FileHotspot(BaseModel):
    """Most-touched files."""
    file_path: str
    edit_count: int = 0
    write_count: int = 0
    total_touches: int = 0
    loc_written: int = 0
    language: Optional[str] = None


class ProductivityResponse(BaseModel):
    """Complete productivity data."""
    summary: EfficiencySummary
    loc_trend: List[LocTrendPoint]
    languages: List[LanguageBreakdown]
    tool_usage: List[ToolUsageStat]
    error_analysis: ErrorAnalysis
    file_hotspots: List[FileHotspot]
