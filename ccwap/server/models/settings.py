"""Pydantic models for settings API."""

from typing import Dict, Optional, Any
from pydantic import BaseModel


class PricingEntry(BaseModel):
    """Pricing for a single model."""
    input: float
    output: float
    cache_read: float
    cache_write_5m: float
    cache_write_1h: float
    # Legacy alias preserved for backward compatibility.
    cache_write: float = 0.0


class PricingUpdateRequest(BaseModel):
    """Request to update model pricing."""
    model: str
    pricing: PricingEntry


class EtlStatus(BaseModel):
    """ETL pipeline status."""
    files_total: int = 0
    files_processed: int = 0
    last_run: Optional[str] = None
    database_size_bytes: int = 0


class DatabaseStats(BaseModel):
    """Database table counts."""
    sessions: int = 0
    turns: int = 0
    tool_calls: int = 0
    experiment_tags: int = 0
    daily_summaries: int = 0
    etl_state: int = 0
    snapshots: int = 0
    saved_views: int = 0
    alert_rules: int = 0


class SettingsResponse(BaseModel):
    """Complete settings data."""
    pricing: Dict[str, PricingEntry]
    etl_status: EtlStatus
    db_stats: DatabaseStats
    version: str = ""
