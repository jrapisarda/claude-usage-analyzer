"""Shared date helpers for query modules.

Centralizes date filter construction with localtime conversion.
All UTC timestamps stored in SQLite are converted to local time at query boundaries.
"""

from datetime import date
from typing import Optional


def local_today() -> str:
    """Return today's date in local time as YYYY-MM-DD."""
    return date.today().isoformat()


def build_date_filter(
    col: str,
    date_from: Optional[str],
    date_to: Optional[str],
    params: list,
) -> str:
    """Build SQL WHERE clauses with localtime conversion.

    Converts UTC timestamps to local time before comparison.
    Returns string like: " AND date(col, 'localtime') >= ? AND date(col, 'localtime') <= ?"
    Appends values to params list.
    """
    clauses = ""
    if date_from:
        clauses += f" AND date({col}, 'localtime') >= ?"
        params.append(date_from)
    if date_to:
        clauses += f" AND date({col}, 'localtime') <= ?"
        params.append(date_to)
    return clauses


def build_summary_filter(
    date_from: Optional[str],
    date_to: Optional[str],
    params: list,
) -> str:
    """Build SQL WHERE clauses for daily_summaries table.

    daily_summaries dates are already in local time, no conversion needed.
    Returns string like: " AND date >= ? AND date <= ?"
    """
    clauses = ""
    if date_from:
        clauses += " AND date >= ?"
        params.append(date_from)
    if date_to:
        clauses += " AND date <= ?"
        params.append(date_to)
    return clauses
