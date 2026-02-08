"""Pydantic models for heatmap API."""

from typing import List

from pydantic import BaseModel


class HeatmapCell(BaseModel):
    day: int  # 0=Monday, 6=Sunday
    hour: int  # 0-23
    value: float


class HeatmapResponse(BaseModel):
    cells: List[HeatmapCell]
    metric: str
    max_value: float
