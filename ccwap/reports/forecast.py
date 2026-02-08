"""
Forecast report for CCWAP.

Generates the --forecast view with spend projection.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_currency, format_number,
    bold, colorize, Colors
)


def generate_forecast(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    color_enabled: bool = True
) -> str:
    """
    Generate spend projection report.

    Uses historical daily averages to project future spend.

    Args:
        conn: Database connection
        config: Configuration dict
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("SPEND FORECAST", color_enabled))
    lines.append("")

    now = datetime.now()

    # Get last 30 days of cost data
    cursor = conn.execute("""
        SELECT
            date(timestamp) as date,
            SUM(cost) as daily_cost
        FROM turns
        WHERE date(timestamp) >= date(?, '-30 days')
        AND date(timestamp) <= date(?)
        GROUP BY date(timestamp)
        ORDER BY date DESC
    """, (now.strftime('%Y-%m-%d'), now.strftime('%Y-%m-%d')))

    rows = cursor.fetchall()

    if not rows or len(rows) < 7:
        return lines[0] + "\n\nNot enough data for forecast (need at least 7 days)."

    # Calculate averages
    costs = [r['daily_cost'] or 0 for r in rows]
    total_30d = sum(costs)
    avg_daily = total_30d / len(rows)

    # Last 7 days average (more recent trend)
    last_7d_costs = costs[:7] if len(costs) >= 7 else costs
    avg_7d = sum(last_7d_costs) / len(last_7d_costs)

    lines.append(bold("HISTORICAL AVERAGES", color_enabled))
    lines.append("-" * 40)
    lines.append(f"30-day daily average:  {format_currency(avg_daily)}")
    lines.append(f"7-day daily average:   {format_currency(avg_7d)}")
    lines.append("")

    # Projections based on 7-day average (more responsive to recent trends)
    lines.append(bold("PROJECTIONS (based on 7-day trend)", color_enabled))
    lines.append("-" * 40)

    # Days remaining in month
    days_in_month = 30  # Approximate
    first_of_next_month = (now.replace(day=1) + timedelta(days=32)).replace(day=1)
    days_remaining = (first_of_next_month - now).days

    # This month projection
    cursor_month = conn.execute("""
        SELECT SUM(cost) as mtd_cost
        FROM turns
        WHERE strftime('%Y-%m', timestamp) = strftime('%Y-%m', 'now')
    """)
    mtd = cursor_month.fetchone()
    mtd_cost = mtd['mtd_cost'] or 0

    projected_month = mtd_cost + (avg_7d * days_remaining)
    lines.append(f"Month-to-date:         {format_currency(mtd_cost)}")
    lines.append(f"Days remaining:        {days_remaining}")
    lines.append(f"Projected month end:   {format_currency(projected_month)}")
    lines.append("")

    # Weekly/monthly projections
    weekly_projection = avg_7d * 7
    monthly_projection = avg_7d * 30

    lines.append(bold("ESTIMATED RECURRING COSTS", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Weekly:                {format_currency(weekly_projection)}")
    lines.append(f"Monthly:               {format_currency(monthly_projection)}")
    lines.append(f"Yearly (projected):    {format_currency(monthly_projection * 12)}")
    lines.append("")

    # Trend indicator
    if len(costs) >= 14:
        first_half = sum(costs[7:14]) / 7
        second_half = sum(costs[:7]) / 7

        if second_half > first_half * 1.1:
            trend = colorize("INCREASING", Colors.RED, color_enabled)
            pct = ((second_half / first_half) - 1) * 100
            trend += f" (+{format_number(pct, 1)}%)"
        elif second_half < first_half * 0.9:
            trend = colorize("DECREASING", Colors.GREEN, color_enabled)
            pct = (1 - (second_half / first_half)) * 100
            trend += f" (-{format_number(pct, 1)}%)"
        else:
            trend = colorize("STABLE", Colors.YELLOW, color_enabled)

        lines.append(bold("TREND", color_enabled))
        lines.append("-" * 40)
        lines.append(f"7-day trend:           {trend}")

    return '\n'.join(lines)
