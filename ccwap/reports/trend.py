"""
Trend report for CCWAP.

Generates the --trend view with ASCII trend charts.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from ccwap.output.formatter import (
    format_currency, format_number, format_tokens,
    bold, colorize, Colors
)


def parse_period(period: str) -> int:
    """
    Parse period string to number of weeks.

    Supports: 4w, 8w, 12w, etc.
    """
    if period.endswith('w'):
        try:
            return int(period[:-1])
        except ValueError:
            pass
    elif period.endswith('d'):
        try:
            days = int(period[:-1])
            return max(1, days // 7)
        except ValueError:
            pass

    return 8  # Default to 8 weeks


def generate_trend(
    conn: sqlite3.Connection,
    metric: str,
    config: Dict[str, Any],
    period: Optional[str] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate trend chart for a metric.

    Args:
        conn: Database connection
        metric: Metric to chart (cost, tokens, sessions, loc)
        config: Configuration dict
        period: Time period (e.g., 8w for 8 weeks)
        color_enabled: Whether to apply colors
    """
    weeks = parse_period(period) if period else 8

    lines = []
    lines.append(bold(f"TREND: {metric.upper()} (last {weeks} weeks)", color_enabled))
    lines.append("=" * 60)
    lines.append("")

    # Get weekly data
    data = _get_weekly_metric(conn, metric, weeks)

    if not data:
        return lines[0] + "\n\nNo data available."

    # Find min/max for scaling
    values = [d['value'] for d in data]
    max_val = max(values) if values else 1
    min_val = min(values) if values else 0

    # ASCII chart parameters
    chart_width = 50
    chart_height = 10

    # Create chart
    lines.append(_create_ascii_chart(data, metric, chart_width, chart_height, color_enabled))

    # Statistics
    lines.append("")
    lines.append(bold("STATISTICS", color_enabled))
    lines.append("-" * 40)

    formatter = _get_formatter(metric)
    lines.append(f"Max:     {formatter(max_val)}")
    lines.append(f"Min:     {formatter(min_val)}")
    lines.append(f"Average: {formatter(sum(values) / len(values) if values else 0)}")

    # Trend direction
    if len(values) >= 2:
        first_half = sum(values[:len(values)//2]) / (len(values)//2)
        second_half = sum(values[len(values)//2:]) / (len(values) - len(values)//2)

        if second_half > first_half * 1.1:
            trend = colorize("INCREASING", Colors.RED if metric == 'cost' else Colors.GREEN, color_enabled)
        elif second_half < first_half * 0.9:
            trend = colorize("DECREASING", Colors.GREEN if metric == 'cost' else Colors.RED, color_enabled)
        else:
            trend = colorize("STABLE", Colors.YELLOW, color_enabled)

        lines.append(f"Trend:   {trend}")

    return '\n'.join(lines)


def _get_weekly_metric(
    conn: sqlite3.Connection,
    metric: str,
    weeks: int
) -> List[Dict[str, Any]]:
    """Get weekly values for a metric."""
    end_date = datetime.now()
    start_date = end_date - timedelta(weeks=weeks)

    if metric == 'cost':
        query = """
            SELECT
                strftime('%Y-W%W', timestamp) as week,
                SUM(cost) as value
            FROM turns
            WHERE date(timestamp) >= date(?)
            GROUP BY week
            ORDER BY week
        """
    elif metric == 'tokens':
        query = """
            SELECT
                strftime('%Y-W%W', timestamp) as week,
                SUM(input_tokens + output_tokens) as value
            FROM turns
            WHERE date(timestamp) >= date(?)
            GROUP BY week
            ORDER BY week
        """
    elif metric == 'sessions':
        query = """
            SELECT
                strftime('%Y-W%W', first_timestamp) as week,
                COUNT(*) as value
            FROM sessions
            WHERE date(first_timestamp) >= date(?)
            GROUP BY week
            ORDER BY week
        """
    elif metric == 'loc':
        query = """
            SELECT
                strftime('%Y-W%W', timestamp) as week,
                SUM(loc_written) as value
            FROM tool_calls
            WHERE date(timestamp) >= date(?)
            GROUP BY week
            ORDER BY week
        """
    else:
        return []

    cursor = conn.execute(query, (start_date.strftime('%Y-%m-%d'),))
    return [{'week': r['week'], 'value': r['value'] or 0} for r in cursor.fetchall()]


def _get_formatter(metric: str):
    """Get the appropriate formatter for a metric."""
    if metric == 'cost':
        return format_currency
    elif metric == 'tokens':
        return format_tokens
    else:
        return format_number


def _create_ascii_chart(
    data: List[Dict[str, Any]],
    metric: str,
    width: int,
    height: int,
    color_enabled: bool
) -> str:
    """Create an ASCII line chart."""
    if not data:
        return "No data"

    values = [d['value'] for d in data]
    max_val = max(values) if values else 1
    min_val = min(values) if values else 0
    range_val = max_val - min_val if max_val != min_val else 1

    formatter = _get_formatter(metric)
    lines = []

    # Y-axis labels width
    y_label_width = 12

    # Create chart rows
    chart = []
    for row in range(height):
        threshold = max_val - (range_val * row / (height - 1))
        line = ""
        for i, val in enumerate(values):
            if val >= threshold:
                line += "#"
            else:
                line += " "

        # Pad to width
        if len(line) < width:
            line = line.ljust(width)

        chart.append(line)

    # Add Y-axis labels
    lines.append(f"{formatter(max_val):>{y_label_width}} |" + chart[0])
    for row in range(1, height - 1):
        lines.append(" " * y_label_width + " |" + chart[row])
    lines.append(f"{formatter(min_val):>{y_label_width}} |" + chart[-1])

    # X-axis
    lines.append(" " * y_label_width + " +" + "-" * len(values))

    # X-axis labels (first and last week)
    if data:
        first_week = data[0]['week']
        last_week = data[-1]['week']
        x_labels = " " * y_label_width + f"  {first_week}" + " " * (len(values) - len(first_week) - len(last_week) - 2) + last_week
        lines.append(x_labels)

    return '\n'.join(lines)
