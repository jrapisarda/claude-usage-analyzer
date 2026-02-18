"""
Cost calculation for CCWAP.

This module is THE central cost calculation logic that fixes bugs 1-6 from
the old tool. All costs MUST flow through calculate_turn_cost().

CRITICAL: Never use flat-rate calculations. Always use:
- Per-model pricing
- Per-token-type pricing (input, output, cache hits/refreshes, cache writes)
"""

from typing import Dict, Any, List, Optional
from ccwap.cost.pricing import get_pricing_for_model


def _calculate_cache_write_cost(
    cache_write_tokens: int,
    ephemeral_5m_tokens: int,
    ephemeral_1h_tokens: int,
    pricing: Dict[str, float],
) -> float:
    """
    Calculate cache write cost across 5m/1h TTL tiers.

    Backward compatibility:
    - If tiered tokens are unavailable, falls back to legacy cache_write_tokens
      at the 5m write rate.
    - If tiered tokens are partially available, any remainder uses 5m rate.
    """
    write_5m_rate = pricing.get("cache_write_5m", pricing.get("cache_write", 0.0))
    write_1h_rate = pricing.get("cache_write_1h", write_5m_rate * 1.6)

    cache_write_tokens = max(0, cache_write_tokens or 0)
    ephemeral_5m_tokens = max(0, ephemeral_5m_tokens or 0)
    ephemeral_1h_tokens = max(0, ephemeral_1h_tokens or 0)

    tiered_total = ephemeral_5m_tokens + ephemeral_1h_tokens
    if tiered_total == 0:
        return (cache_write_tokens / 1_000_000) * write_5m_rate

    legacy_remainder = max(0, cache_write_tokens - tiered_total)
    return (
        (ephemeral_5m_tokens / 1_000_000) * write_5m_rate
        + (ephemeral_1h_tokens / 1_000_000) * write_1h_rate
        + (legacy_remainder / 1_000_000) * write_5m_rate
    )


def calculate_turn_cost(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    model: Optional[str],
    config: Dict[str, Any],
    ephemeral_5m_tokens: int = 0,
    ephemeral_1h_tokens: int = 0,
) -> float:
    """
    Calculate accurate cost for a single turn.

    This is THE central cost calculation function. ALL costs flow through here.
    Per-token-type pricing, per-model. NEVER uses flat rates.

    FIXES BUGS 1-6 from the old tool:
    - Bug 1: Daily view flat-rate cost
    - Bug 2: Weekly view flat-rate cost
    - Bug 3: Comparison view flat-rate cost
    - Bug 4: Forecast view flat-rate cost
    - Bug 5: Default model pricing in project view
    - Bug 6: Arbitrary model selection for session cost

    Args:
        input_tokens: Fresh input tokens (not cached)
        output_tokens: Output/completion tokens
        cache_read_tokens: Tokens read from cache
        cache_write_tokens: Legacy cache write token total
        model: Model identifier for pricing lookup
        config: Configuration dict with pricing table
        ephemeral_5m_tokens: Cache creation tokens at 5m TTL
        ephemeral_1h_tokens: Cache creation tokens at 1h TTL

    Returns:
        Cost in dollars for this turn
    """
    # Get pricing for this specific model
    pricing = get_pricing_for_model(model, config)

    # Ensure non-negative token counts (validation)
    input_tokens = max(0, input_tokens or 0)
    output_tokens = max(0, output_tokens or 0)
    cache_read_tokens = max(0, cache_read_tokens or 0)
    cache_write_cost = _calculate_cache_write_cost(
        cache_write_tokens=cache_write_tokens,
        ephemeral_5m_tokens=ephemeral_5m_tokens,
        ephemeral_1h_tokens=ephemeral_1h_tokens,
        pricing=pricing,
    )

    # Calculate cost per token type (prices are per 1M tokens)
    cost = (
        (input_tokens / 1_000_000) * pricing['input'] +
        (output_tokens / 1_000_000) * pricing['output'] +
        (cache_read_tokens / 1_000_000) * pricing['cache_read'] +
        cache_write_cost
    )

    return cost


def calculate_session_cost(
    turns: List[Dict[str, Any]],
    config: Dict[str, Any]
) -> float:
    """
    Calculate total cost for a session by summing per-turn costs.

    Each turn uses its OWN model for pricing. This fixes Bug 6 where
    the old tool picked an arbitrary model from the set.

    Args:
        turns: List of turn dicts, each with token counts and model
        config: Configuration dict with pricing table

    Returns:
        Total session cost in dollars
    """
    total = 0.0
    for turn in turns:
        total += calculate_turn_cost(
            input_tokens=turn.get('input_tokens', 0),
            output_tokens=turn.get('output_tokens', 0),
            cache_read_tokens=turn.get('cache_read_tokens', 0),
            cache_write_tokens=turn.get('cache_write_tokens', 0),
            model=turn.get('model'),
            config=config,
            ephemeral_5m_tokens=turn.get('ephemeral_5m_tokens', 0),
            ephemeral_1h_tokens=turn.get('ephemeral_1h_tokens', 0),
        )
    return total


def calculate_cost_breakdown(
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
    cache_write_tokens: int,
    model: Optional[str],
    config: Dict[str, Any],
    ephemeral_5m_tokens: int = 0,
    ephemeral_1h_tokens: int = 0,
) -> Dict[str, float]:
    """
    Calculate cost with breakdown by token type.

    Useful for detailed reporting showing where costs come from.

    Returns:
        Dict with keys: input_cost, output_cost, cache_read_cost,
        cache_write_5m_cost, cache_write_1h_cost, cache_write_cost, total_cost
    """
    pricing = get_pricing_for_model(model, config)

    # Ensure non-negative
    input_tokens = max(0, input_tokens or 0)
    output_tokens = max(0, output_tokens or 0)
    cache_read_tokens = max(0, cache_read_tokens or 0)
    cache_write_tokens = max(0, cache_write_tokens or 0)
    ephemeral_5m_tokens = max(0, ephemeral_5m_tokens or 0)
    ephemeral_1h_tokens = max(0, ephemeral_1h_tokens or 0)

    input_cost = (input_tokens / 1_000_000) * pricing['input']
    output_cost = (output_tokens / 1_000_000) * pricing['output']
    cache_read_cost = (cache_read_tokens / 1_000_000) * pricing['cache_read']
    cache_write_5m_rate = pricing.get("cache_write_5m", pricing.get("cache_write", 0.0))
    cache_write_1h_rate = pricing.get("cache_write_1h", cache_write_5m_rate * 1.6)

    tiered_total = ephemeral_5m_tokens + ephemeral_1h_tokens
    if tiered_total == 0:
        cache_write_5m_cost = (cache_write_tokens / 1_000_000) * cache_write_5m_rate
        cache_write_1h_cost = 0.0
    else:
        legacy_remainder = max(0, cache_write_tokens - tiered_total)
        cache_write_5m_cost = ((ephemeral_5m_tokens + legacy_remainder) / 1_000_000) * cache_write_5m_rate
        cache_write_1h_cost = (ephemeral_1h_tokens / 1_000_000) * cache_write_1h_rate

    cache_write_cost = cache_write_5m_cost + cache_write_1h_cost

    return {
        'input_cost': input_cost,
        'output_cost': output_cost,
        'cache_read_cost': cache_read_cost,
        'cache_write_5m_cost': cache_write_5m_cost,
        'cache_write_1h_cost': cache_write_1h_cost,
        'cache_write_cost': cache_write_cost,
        'total_cost': input_cost + output_cost + cache_read_cost + cache_write_cost
    }


def format_cost(cost: float) -> str:
    """Format cost as currency string."""
    return f"${cost:,.2f}"


def format_cost_per_k(cost: float, count: int, unit: str = "tokens") -> str:
    """Format cost per 1000 units."""
    if count == 0:
        return "N/A"
    cost_per_k = cost / (count / 1000)
    return f"${cost_per_k:,.4f}/K{unit}"
