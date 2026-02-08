"""
Timestamp utilities for CCWAP.

Handles parsing and conversion of timestamps from JSONL files.
JSONL timestamps are UTC with 'Z' suffix.
"""

from datetime import datetime, timezone
from typing import Optional


def parse_timestamp(ts: Optional[str]) -> Optional[datetime]:
    """
    Parse ISO-8601 timestamp with Z suffix to datetime.

    JSONL files use UTC timestamps with 'Z' suffix.
    Returns None if parsing fails.

    Args:
        ts: Timestamp string like "2026-01-15T10:30:00.123Z"

    Returns:
        datetime object in UTC, or None if parsing failed
    """
    if not ts:
        return None

    try:
        # Handle 'Z' suffix (UTC indicator)
        if ts.endswith('Z'):
            ts = ts[:-1] + '+00:00'

        return datetime.fromisoformat(ts)
    except (ValueError, TypeError):
        return None


def to_local_display(utc_dt: Optional[datetime]) -> str:
    """
    Convert UTC datetime to local timezone for display.

    Args:
        utc_dt: datetime object (should be UTC)

    Returns:
        Formatted string in local timezone, or "N/A" if None
    """
    if not utc_dt:
        return "N/A"

    # Ensure timezone awareness
    if utc_dt.tzinfo is None:
        utc_dt = utc_dt.replace(tzinfo=timezone.utc)

    local_dt = utc_dt.astimezone()
    return local_dt.strftime('%Y-%m-%d %H:%M:%S')


def to_date_string(dt: Optional[datetime]) -> str:
    """
    Convert datetime to date string (YYYY-MM-DD).

    Args:
        dt: datetime object

    Returns:
        Date string or "N/A" if None
    """
    if not dt:
        return "N/A"
    return dt.strftime('%Y-%m-%d')


def to_iso_string(dt: Optional[datetime]) -> Optional[str]:
    """
    Convert datetime to ISO-8601 string for storage.

    Args:
        dt: datetime object

    Returns:
        ISO format string or None if input is None
    """
    if not dt:
        return None
    return dt.isoformat()


def get_date_from_timestamp(ts: Optional[str]) -> Optional[str]:
    """
    Extract date (YYYY-MM-DD) from timestamp string.

    Faster than full parse when only date is needed.
    """
    if not ts or len(ts) < 10:
        return None
    return ts[:10]
