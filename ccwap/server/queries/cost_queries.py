"""Cost analysis query module."""

from datetime import date, timedelta
from typing import Optional, Dict, Any, List

import aiosqlite

from ccwap.server.queries.date_helpers import local_today, build_date_filter


async def _get_daily_cost_rows_from_turns(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Any]:
    """Return daily cost rows from live turns data for accurate near-real-time metrics."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            date(timestamp, 'localtime') as day,
            SUM(cost) as cost
        FROM turns
        WHERE timestamp IS NOT NULL {filters}
        GROUP BY day
        ORDER BY day ASC
    """, params)
    return await cursor.fetchall()


async def _get_cost_sum_from_turns(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> float:
    """Return summed cost from live turns data for a date range."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT SUM(cost)
        FROM turns
        WHERE timestamp IS NOT NULL {filters}
    """, params)
    row = await cursor.fetchone()
    return row[0] or 0.0


async def get_cost_summary(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Cost summary cards: total, avg daily, today, this week, this month."""
    today = date.today()
    today_str = local_today()
    week_start = (today - timedelta(days=today.weekday())).isoformat()
    month_start = today.replace(day=1).isoformat()

    # Date-range total/average from live daily aggregates.
    daily_rows = await _get_daily_cost_rows_from_turns(db, date_from, date_to)
    total_cost = sum((row[1] or 0.0) for row in daily_rows)
    day_count = len(daily_rows)
    avg_daily = (total_cost / day_count) if day_count > 0 else 0.0

    # Rolling windows from live turns to avoid stale daily_summaries.
    cost_today = await _get_cost_sum_from_turns(db, today_str, today_str)
    cost_this_week = await _get_cost_sum_from_turns(db, week_start, today_str)
    cost_this_month = await _get_cost_sum_from_turns(db, month_start, today_str)

    # Projected monthly
    days_elapsed = today.day
    projected_monthly = (cost_this_month / days_elapsed * 30) if days_elapsed > 0 else 0.0

    return {
        "total_cost": total_cost,
        "avg_daily_cost": avg_daily,
        "cost_today": cost_today,
        "cost_this_week": cost_this_week,
        "cost_this_month": cost_this_month,
        "projected_monthly": projected_monthly,
    }


async def get_cost_by_token_type(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    config: Optional[dict] = None,
) -> Dict[str, float]:
    """Cost breakdown by token type using pre-calculated turn costs."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(cache_write_tokens) as cache_write_tokens,
            SUM(cost) as total_cost
        FROM turns
        WHERE timestamp IS NOT NULL {filters}
    """, params)
    row = await cursor.fetchone()

    total_cost = row[4] or 0.0
    total_tokens = (row[0] or 0) + (row[1] or 0) + (row[2] or 0) + (row[3] or 0)

    if total_tokens == 0:
        return {"input_cost": 0, "output_cost": 0, "cache_read_cost": 0, "cache_write_cost": 0, "total_cost": 0}

    # Approximate cost split proportional to token counts weighted by avg cost
    # Use default sonnet rates as weight factors
    input_w = (row[0] or 0) * 3.0
    output_w = (row[1] or 0) * 15.0
    cache_read_w = (row[2] or 0) * 0.30
    cache_write_w = (row[3] or 0) * 3.75
    total_w = input_w + output_w + cache_read_w + cache_write_w

    if total_w == 0:
        return {"input_cost": 0, "output_cost": 0, "cache_read_cost": 0, "cache_write_cost": 0, "total_cost": total_cost}

    return {
        "input_cost": total_cost * (input_w / total_w),
        "output_cost": total_cost * (output_w / total_w),
        "cache_read_cost": total_cost * (cache_read_w / total_w),
        "cache_write_cost": total_cost * (cache_write_w / total_w),
        "total_cost": total_cost,
    }


async def get_cost_by_model(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Cost breakdown by model."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            model,
            SUM(cost) as cost,
            COUNT(*) as turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens
        FROM turns
        WHERE model IS NOT NULL AND model NOT LIKE '<%' {filters}
        GROUP BY model
        ORDER BY cost DESC
    """, params)
    rows = await cursor.fetchall()

    total_cost = sum(r[1] or 0 for r in rows)
    return [
        {
            "model": row[0],
            "cost": row[1] or 0.0,
            "turns": row[2] or 0,
            "input_tokens": row[3] or 0,
            "output_tokens": row[4] or 0,
            "percentage": ((row[1] or 0) / total_cost * 100) if total_cost > 0 else 0.0,
        }
        for row in rows
    ]


async def get_cost_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daily cost trend with cumulative total."""
    rows = await _get_daily_cost_rows_from_turns(db, date_from, date_to)

    cumulative = 0.0
    result = []
    for row in rows:
        cumulative += row[1] or 0
        result.append({
            "date": row[0],
            "cost": row[1] or 0.0,
            "cumulative_cost": cumulative,
        })
    return result


async def get_cost_by_project(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 10,
) -> List[Dict[str, Any]]:
    """Top projects by cost."""
    params: list = []
    filters = build_date_filter("t.timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            s.project_path,
            s.project_display,
            SUM(t.cost) as cost
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE t.timestamp IS NOT NULL {filters}
        GROUP BY s.project_path
        ORDER BY cost DESC
        LIMIT ?
    """, params + [limit])
    rows = await cursor.fetchall()

    total_cost = sum(r[2] or 0 for r in rows)
    return [
        {
            "project_path": row[0],
            "project_display": row[1] or row[0],
            "cost": row[2] or 0.0,
            "percentage": ((row[2] or 0) / total_cost * 100) if total_cost > 0 else 0.0,
        }
        for row in rows
    ]


async def get_cache_savings(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Cache savings analysis."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(input_tokens) as input_tokens,
            SUM(cost) as actual_cost
        FROM turns
        WHERE timestamp IS NOT NULL {filters}
    """, params)
    row = await cursor.fetchone()

    cache_read = row[0] or 0
    input_tokens = row[1] or 0
    actual_cost = row[2] or 0.0
    total_input = input_tokens + cache_read
    cache_hit_rate = cache_read / total_input if total_input > 0 else 0.0

    # Estimate cost without cache: cache_read tokens would have been full-price input
    # Approximate savings using default sonnet input rate ($3/M) vs cache rate ($0.30/M)
    savings_per_token = (3.00 - 0.30) / 1_000_000
    estimated_savings = cache_read * savings_per_token
    cost_without_cache = actual_cost + estimated_savings

    return {
        "total_cache_read_tokens": cache_read,
        "total_input_tokens": input_tokens,
        "cache_hit_rate": cache_hit_rate,
        "estimated_savings": estimated_savings,
        "cost_without_cache": cost_without_cache,
        "actual_cost": actual_cost,
    }


async def get_cost_anomalies(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daily cost with anomaly detection via IQR method.
    Returns list of dicts with: date, cost, is_anomaly, threshold."""
    rows = await _get_daily_cost_rows_from_turns(db, date_from, date_to)

    if not rows:
        return []

    costs = sorted([r[1] or 0 for r in rows])
    n = len(costs)
    if n >= 4:
        from statistics import quantiles
        q1, _median, q3 = quantiles(costs, n=4)
    else:
        q1 = costs[0]
        q3 = costs[-1]
    iqr = q3 - q1
    threshold = q3 + 1.5 * iqr

    return [
        {
            "date": row[0],
            "cost": row[1] or 0.0,
            "is_anomaly": (row[1] or 0) > threshold,
            "threshold": threshold,
        }
        for row in rows
    ]


async def get_cumulative_cost(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Running sum of daily cost.
    Returns list of dicts with: date, daily_cost, cumulative."""
    rows = await _get_daily_cost_rows_from_turns(db, date_from, date_to)

    cumulative = 0.0
    result = []
    for row in rows:
        daily = row[1] or 0.0
        cumulative += daily
        result.append({
            "date": row[0],
            "daily_cost": daily,
            "cumulative": cumulative,
        })
    return result


async def get_cache_simulation(
    db: aiosqlite.Connection,
    target_hit_rate: float = 0.5,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """What-if: calculate cost savings if cache hit rate improved.
    Returns dict with: actual_cost, actual_cache_rate, simulated_cost, simulated_cache_rate, savings."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            SUM(input_tokens) as input_tokens,
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(cost) as actual_cost
        FROM turns
        WHERE timestamp IS NOT NULL {filters}
    """, params)
    row = await cursor.fetchone()

    input_tokens = row[0] or 0
    cache_read = row[1] or 0
    actual_cost = row[2] or 0.0
    total_input = input_tokens + cache_read

    actual_cache_rate = cache_read / total_input if total_input > 0 else 0.0

    if total_input == 0 or target_hit_rate <= actual_cache_rate:
        return {
            "actual_cost": actual_cost,
            "actual_cache_rate": actual_cache_rate,
            "simulated_cost": actual_cost,
            "simulated_cache_rate": target_hit_rate,
            "savings": 0.0,
        }

    # Simulate: if cache_read increased to target_hit_rate of total_input
    simulated_cache_read = total_input * target_hit_rate
    simulated_input = total_input - simulated_cache_read

    # Tokens that shift from full-price input to cache-price
    tokens_shifted = simulated_cache_read - cache_read
    # Pricing: input=$3/Mtok, cache_read=$0.30/Mtok
    savings = tokens_shifted * (3.00 - 0.30) / 1_000_000
    simulated_cost = actual_cost - savings

    return {
        "actual_cost": actual_cost,
        "actual_cache_rate": actual_cache_rate,
        "simulated_cost": simulated_cost,
        "simulated_cache_rate": target_hit_rate,
        "savings": savings,
    }


async def get_spend_forecast(
    db: aiosqlite.Connection,
) -> Dict[str, Any]:
    """14-day spend forecast based on recent trends."""
    today = date.today()
    today_str = local_today()
    start = (today - timedelta(days=13)).isoformat()

    rows = await _get_daily_cost_rows_from_turns(db, start, today_str)

    if not rows:
        return {
            "daily_avg": 0,
            "projected_7d": 0,
            "projected_14d": 0,
            "projected_30d": 0,
            "trend_direction": "stable",
            "confidence": 0,
        }

    costs = [r[1] or 0 for r in rows]
    daily_avg = sum(costs) / len(costs) if costs else 0

    # Simple trend: compare first half to second half
    mid = len(costs) // 2
    first_half_avg = sum(costs[:mid]) / mid if mid > 0 else 0
    second_half_avg = sum(costs[mid:]) / (len(costs) - mid) if len(costs) - mid > 0 else 0

    if daily_avg > 0 and first_half_avg > 0:
        trend_ratio = second_half_avg / first_half_avg
        if trend_ratio > 1.1:
            trend_direction = "increasing"
        elif trend_ratio < 0.9:
            trend_direction = "decreasing"
        else:
            trend_direction = "stable"
    else:
        trend_direction = "stable"

    confidence = min(len(costs) / 14.0, 1.0)

    return {
        "daily_avg": daily_avg,
        "projected_7d": daily_avg * 7,
        "projected_14d": daily_avg * 14,
        "projected_30d": daily_avg * 30,
        "trend_direction": trend_direction,
        "confidence": confidence,
    }
