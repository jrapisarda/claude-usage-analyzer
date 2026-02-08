"""
Pricing table management for CCWAP.

Handles loading and lookup of model pricing information.
Separated from calculator for cleaner architecture per review.
"""

from typing import Dict, Any, Optional

# Default pricing: cost per 1M tokens
DEFAULT_PRICING: Dict[str, Dict[str, float]] = {
    "claude-opus-4-6": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write": 6.25
    },
    "claude-opus-4-5-20251101": {
        "input": 5.00,
        "output": 25.00,
        "cache_read": 0.50,
        "cache_write": 6.25
    },
    "claude-sonnet-4-5-20250929": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75
    },
    "claude-sonnet-4-20250514": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75
    },
    "claude-3-5-sonnet-20241022": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75
    },
    "claude-haiku-3-5-20241022": {
        "input": 0.80,
        "output": 4.00,
        "cache_read": 0.08,
        "cache_write": 1.00
    },
    "claude-haiku-4-5-20251001": {
        "input": 1.00,
        "output": 5.00,
        "cache_read": 0.10,
        "cache_write": 1.25
    },
    "default": {
        "input": 3.00,
        "output": 15.00,
        "cache_read": 0.30,
        "cache_write": 3.75
    }
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
        Dict with keys: input, output, cache_read, cache_write
        All values are cost per 1M tokens
    """
    if not model:
        return config.get('pricing', DEFAULT_PRICING).get('default', DEFAULT_PRICING['default'])

    pricing_table = config.get('pricing', DEFAULT_PRICING)

    # Exact match
    if model in pricing_table:
        return pricing_table[model]

    # Prefix match for model families
    for known_model in pricing_table:
        if known_model == 'default':
            continue

        # Check if known model is a prefix
        if model.startswith(known_model):
            return pricing_table[known_model]

        # Check if they share a common base before date suffix
        # e.g., "claude-sonnet-4" from "claude-sonnet-4-20250514"
        base = known_model.rsplit('-', 1)[0]
        if model.startswith(base):
            return pricing_table[known_model]

    # Silently use default pricing for synthetic/internal models
    if not model.startswith('<'):
        import sys
        print(f"Warning: Unknown model '{model}', using default pricing", file=sys.stderr)
    return pricing_table.get('default', DEFAULT_PRICING['default'])


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
