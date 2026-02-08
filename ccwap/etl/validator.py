"""
Validation for CCWAP ETL pipeline.

Centralizes validation rules from requirements Section 3.4.
"""

from typing import Dict, Any, Optional, Tuple
from ccwap.utils.timestamps import parse_timestamp


class ValidationResult:
    """Result of validating an entry."""

    def __init__(self, valid: bool, reason: Optional[str] = None):
        self.valid = valid
        self.reason = reason

    def __bool__(self):
        return self.valid


def validate_entry(entry: Dict[str, Any]) -> ValidationResult:
    """
    Validate a JSONL entry.

    Validation rules from requirements Section 3.4:
    - Must be valid JSON (handled by parser)
    - Must have valid timestamp
    - Must have non-empty uuid

    Args:
        entry: Parsed JSONL entry dict

    Returns:
        ValidationResult with valid flag and reason if invalid
    """
    # Check UUID
    uuid = entry.get('uuid')
    if not uuid or not isinstance(uuid, str):
        return ValidationResult(False, "Missing or invalid uuid")

    # Check timestamp
    timestamp_str = entry.get('timestamp')
    if not timestamp_str:
        return ValidationResult(False, "Missing timestamp")

    timestamp = parse_timestamp(timestamp_str)
    if not timestamp:
        return ValidationResult(False, f"Invalid timestamp format: {timestamp_str}")

    return ValidationResult(True)


def validate_token_count(value: Any) -> int:
    """
    Validate and normalize a token count.

    Rules:
    - Must be non-negative integer
    - Treat negative values as 0
    - Treat None as 0

    Args:
        value: Token count value from JSONL

    Returns:
        Normalized non-negative integer
    """
    if value is None:
        return 0

    try:
        count = int(value)
        return max(0, count)
    except (TypeError, ValueError):
        return 0


def validate_cost(cost: float) -> Tuple[bool, float]:
    """
    Validate a calculated cost.

    Rules:
    - Must be non-negative
    - Negative cost indicates calculation bug

    Args:
        cost: Calculated cost value

    Returns:
        Tuple of (valid, normalized_cost)
    """
    if cost < 0:
        return (False, 0.0)
    return (True, cost)


def validate_session_id(session_id: Any) -> Optional[str]:
    """
    Validate and normalize a session ID.

    Rules:
    - Must be non-empty string
    - Derive from filename if missing

    Args:
        session_id: Session ID value

    Returns:
        Validated session ID or None if invalid
    """
    if not session_id:
        return None
    if not isinstance(session_id, str):
        return str(session_id)
    return session_id if session_id.strip() else None


def validate_model(model: Any) -> Optional[str]:
    """
    Validate a model identifier.

    Args:
        model: Model identifier from JSONL

    Returns:
        Validated model string or None
    """
    if not model:
        return None
    if not isinstance(model, str):
        return str(model)
    return model.strip() if model.strip() else None
