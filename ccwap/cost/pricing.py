"""
Pricing table management for CCWAP.

Handles loading and lookup of model pricing information.
Separated from calculator for cleaner architecture per review.
"""

from typing import Dict, Any, Optional

# Default pricing: cost per 1M tokens
# cache_read = cache hits/refreshes rate
# cache_write_5m / cache_write_1h = cache creation write rates by TTL tier
DEFAULT_PRICING: Dict[str, Dict[str, float]] = {
    "claude-opus-4-6": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write_5m": 6.25,
        "cache_write_1h": 10.00,
    },
    "claude-opus-4-5": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write_5m": 6.25,
        "cache_write_1h": 10.00,
    },
    "claude-opus-4-5-20251101": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write_5m": 6.25,
        "cache_write_1h": 10.00,
    },
    "claude-opus-4-1": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write_5m": 18.75,
        "cache_write_1h": 30.00,
    },
    "claude-opus-4": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write_5m": 18.75,
        "cache_write_1h": 30.00,
    },
    "claude-opus-3": {
        "input": 15.00,
        "output": 75.00,
        "cache_read": 1.50,
        "cache_write_5m": 18.75,
        "cache_write_1h": 30.00,
    },
    "claude-sonnet-4-6": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
    },
    "claude-sonnet-4-5": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
    },
    "claude-sonnet-4-20250514": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
    },
    "claude-sonnet-3-7": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
    },
    "claude-3-7-sonnet": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
    },
    "claude-haiku-3-5-20241022": {
        "input": 0.80,
        "output": 4.00,
        "cache_read": 0.08,
        "cache_write_5m": 1.00,
        "cache_write_1h": 1.60,
    },
    "claude-haiku-4-5": {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_write_5m": 1.25,
        "cache_write_1h": 2.00,
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_write_5m": 1.25,
        "cache_write_1h": 2.00,
    },
    "claude-haiku-3": {
        "input": 0.25,
        "output": 1.25,
        "cache_read": 0.03,
        "cache_write_5m": 0.30,
        "cache_write_1h": 0.50,
    },
    "default": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write_5m": 3.75,
        "cache_write_1h": 6.00,
    }
}

def _safe_float(value: Any, fallback: float = 0.0) -> float:
    """Best-effort float conversion for pricing values."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return fallback


def normalize_pricing_entry(entry: Dict[str, Any]) -> Dict[str, float]:
    """
    Normalize pricing entry to the full key-set used by calculators.

    Backward compatibility:
    - `cache_write` is treated as the 5m cache write rate.
    - `cache_write_1h` defaults to 1.6x 5m when absent.
    """
    input_rate = _safe_float(entry.get("input"), 0.0)
    output_rate = _safe_float(entry.get("output"), 0.0)
    cache_read_rate = _safe_float(
        entry.get("cache_read", entry.get("cache_hits_refreshes", 0.0)),
        0.0,
    )

    legacy_write = _safe_float(entry.get("cache_write"), 0.0)
    write_5m = _safe_float(entry.get("cache_write_5m"), legacy_write)
    write_1h = _safe_float(entry.get("cache_write_1h"), write_5m * 1.6)

    return {
        "input": input_rate,
        "output": output_rate,
        "cache_read": cache_read_rate,
        "cache_write_5m": write_5m,
        "cache_write_1h": write_1h,
        # Keep legacy alias for existing UI/tests/code paths.
        "cache_write": write_5m,
    }


def get_pricing_for_model(
    model: Optional[str],
    config: Dict[str, Any]
) -> Dict[str, float]:
    """
    Get pricing for a specific model.

    Lookup order:
    1. Exact match in config
    2. Prefix match in config
    3. Default pricing

    Args:
        model: Model identifier (e.g., 'claude-opus-4-5-20251101')
        config: Configuration dict containing 'pricing' key

    Returns:
        Dict with keys:
        - input
        - output
        - cache_read
        - cache_write_5m
        - cache_write_1h
        - cache_write (legacy alias to cache_write_5m)
        All values are cost per 1M tokens
    """
    pricing_table = config.get('pricing', DEFAULT_PRICING)

    if not model:
        return normalize_pricing_entry(
            pricing_table.get('default', DEFAULT_PRICING['default'])
        )

    # Exact match
    if model in pricing_table:
        return normalize_pricing_entry(pricing_table[model])

    # Prefix match for model families
    for known_model in pricing_table:
        if known_model == 'default':
            continue

        # Check if known model is a prefix
        if model.startswith(known_model):
            return normalize_pricing_entry(pricing_table[known_model])

        # Check if they share a common base before date suffix
        # e.g., "claude-sonnet-4" from "claude-sonnet-4-20250514"
        base = known_model.rsplit('-', 1)[0]
        if model.startswith(base):
            return normalize_pricing_entry(pricing_table[known_model])

    # Silently use default pricing for synthetic/internal models
    if not model.startswith('<'):
        import sys
        print(f"Warning: Unknown model '{model}', using default pricing", file=sys.stderr)
    return normalize_pricing_entry(
        pricing_table.get('default', DEFAULT_PRICING['default'])
    )


def is_opus_model(model: Optional[str]) -> bool:
    """Check if model is an Opus variant (most expensive tier)."""
    if not model:
        return False
    return 'opus' in model.lower()


def is_haiku_model(model: Optional[str]) -> bool:
    """Check if model is a Haiku variant (cheapest tier)."""
    if not model:
        return False
    return 'haiku' in model.lower()


def get_pricing_tier(model: Optional[str]) -> str:
    """
    Get the pricing tier name for a model.

    Returns: 'opus', 'sonnet', 'haiku', or 'unknown'
    """
    if not model:
        return 'unknown'

    model_lower = model.lower()
    if 'opus' in model_lower:
        return 'opus'
    elif 'haiku' in model_lower:
        return 'haiku'
    elif 'sonnet' in model_lower:
        return 'sonnet'
    else:
        return 'unknown'
