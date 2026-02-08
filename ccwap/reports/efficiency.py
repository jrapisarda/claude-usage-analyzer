"""
Efficiency report for CCWAP.

Generates the --efficiency view with productivity metrics.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_currency, format_number, format_percentage,
    format_duration, bold, colorize, Colors
)


def generate_efficiency(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate productivity metrics report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("EFFICIENCY METRICS", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build query with optional date filters
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(t.timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(t.timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # Query aggregated stats (turns only - no session join to avoid multiplication)
    cursor = conn.execute(f"""
        SELECT
            COUNT(DISTINCT t.session_id) as sessions,
            COUNT(CASE WHEN t.entry_type = 'user' THEN 1 END) as user_turns,
            SUM(t.input_tokens) as input_tokens,
            SUM(t.output_tokens) as output_tokens,
            SUM(t.cache_read_tokens) as cache_read,
            SUM(t.cache_write_tokens) as cache_write,
            SUM(t.cost) as cost
        FROM turns t
        WHERE 1=1 {date_filter}
    """, params)

    stats = cursor.fetchone()

    if not stats or stats['sessions'] == 0:
        return lines[0] + "\n\nNo data found."

    # Get duration separately from sessions to avoid JOIN multiplication
    duration_filter = date_filter.replace("t.timestamp", "s.first_timestamp")
    cursor = conn.execute(f"""
        SELECT COALESCE(SUM(s.duration_seconds), 0) as duration
        FROM sessions s
        WHERE 1=1 {duration_filter}
    """, params)
    duration_row = cursor.fetchone()

    # Query tool call stats
    tool_filter = date_filter.replace("t.timestamp", "tc.timestamp")
    tool_params = params.copy()

    cursor = conn.execute(f"""
        SELECT
            COUNT(*) as tool_calls,
            SUM(CASE WHEN success = 1 THEN 1 ELSE 0 END) as successes,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as failures,
            SUM(loc_written) as loc_written
        FROM tool_calls tc
        WHERE 1=1 {tool_filter}
    """, tool_params)

    tool_stats = cursor.fetchone()

    # Calculate metrics
    sessions = stats['sessions'] or 0
    user_turns = stats['user_turns'] or 0
    input_tokens = stats['input_tokens'] or 0
    output_tokens = stats['output_tokens'] or 0
    cache_read = stats['cache_read'] or 0
    cache_write = stats['cache_write'] or 0
    cost = stats['cost'] or 0
    duration = duration_row['duration'] or 0

    tool_calls = tool_stats['tool_calls'] or 0
    successes = tool_stats['successes'] or 0
    failures = tool_stats['failures'] or 0
    loc_written = tool_stats['loc_written'] or 0

    # Output metrics
    lines.append(bold("Cost Efficiency", color_enabled))
    lines.append("-" * 40)

    if loc_written > 0:
        cost_per_kloc = cost / (loc_written / 1000)
        lines.append(f"Cost per KLOC:        {format_currency(cost_per_kloc)}")
        tokens_per_loc = output_tokens / loc_written
        lines.append(f"Tokens per LOC:       {format_number(tokens_per_loc, 1)}")

    if user_turns > 0:
        cost_per_turn = cost / user_turns
        lines.append(f"Cost per turn:        {format_currency(cost_per_turn)}")
        loc_per_turn = loc_written / user_turns
        lines.append(f"LOC per turn:         {format_number(loc_per_turn, 1)}")

    if sessions > 0:
        cost_per_session = cost / sessions
        lines.append(f"Cost per session:     {format_currency(cost_per_session)}")
        loc_per_session = loc_written / sessions
        lines.append(f"LOC per session:      {format_number(loc_per_session, 1)}")

    # Thinking cost metrics
    thinking_cursor = conn.execute(f"""
        SELECT
            SUM(t.thinking_chars) as thinking_chars,
            SUM(CASE WHEN t.thinking_chars > 0 THEN t.cost ELSE 0 END) as thinking_cost,
            SUM(t.cost) as total_cost
        FROM turns t
        WHERE 1=1 {date_filter}
    """, params)
    thinking_row = thinking_cursor.fetchone()
    thinking_cost = thinking_row['thinking_cost'] or 0
    thinking_total = thinking_row['total_cost'] or 0
    thinking_pct = (thinking_cost / thinking_total * 100) if thinking_total > 0 else 0
    lines.append(f"Thinking cost:        {format_currency(thinking_cost)}")
    thinking_color = Colors.GREEN if thinking_pct < 20 else Colors.YELLOW if thinking_pct < 40 else Colors.RED
    lines.append(f"Thinking % of cost:   {colorize(format_percentage(thinking_pct), thinking_color, color_enabled)}")

    # Truncation waste metrics
    trunc_cursor = conn.execute(f"""
        SELECT
            SUM(CASE WHEN t.stop_reason = 'max_tokens' THEN t.cost ELSE 0 END) as trunc_cost,
            SUM(CASE WHEN t.stop_reason = 'max_tokens' THEN 1 ELSE 0 END) as trunc_turns,
            COUNT(*) as total_turns
        FROM turns t
        WHERE 1=1 {date_filter}
    """, params)
    trunc_row = trunc_cursor.fetchone()
    trunc_cost = trunc_row['trunc_cost'] or 0
    trunc_turns = trunc_row['trunc_turns'] or 0
    trunc_total_turns = trunc_row['total_turns'] or 0
    trunc_rate = (trunc_turns / trunc_total_turns * 100) if trunc_total_turns > 0 else 0
    lines.append(f"Truncation waste:     {format_currency(trunc_cost)}")
    lines.append(f"Truncated turns:      {format_number(trunc_turns)} ({format_percentage(trunc_rate)})")

    lines.append("")
    lines.append(bold("Cache Efficiency", color_enabled))
    lines.append("-" * 40)

    total_input = input_tokens + cache_read
    if total_input > 0:
        cache_hit_rate = cache_read / total_input * 100
        color = Colors.GREEN if cache_hit_rate > 50 else Colors.YELLOW if cache_hit_rate > 20 else Colors.RED
        rate_str = colorize(format_percentage(cache_hit_rate), color, color_enabled)
        lines.append(f"Cache hit rate:       {rate_str}")

    if cache_read > 0 and input_tokens > 0:
        # Estimate savings from cache
        # Cache reads cost 10x less than input
        cache_savings = (cache_read / 1_000_000) * 15.00 * 0.9  # ~90% savings
        lines.append(f"Est. cache savings:   {format_currency(cache_savings)}")

    lines.append("")
    lines.append(bold("Tool Efficiency", color_enabled))
    lines.append("-" * 40)

    if tool_calls > 0:
        success_rate = successes / tool_calls * 100
        color = Colors.GREEN if success_rate > 95 else Colors.YELLOW if success_rate > 80 else Colors.RED
        rate_str = colorize(format_percentage(success_rate), color, color_enabled)
        lines.append(f"Tool success rate:    {rate_str}")
        lines.append(f"Tool calls:           {format_number(tool_calls)}")
        lines.append(f"Failed calls:         {format_number(failures)}")

    if loc_written > 0 and failures > 0:
        errors_per_kloc = failures / (loc_written / 1000)
        lines.append(f"Errors per KLOC:      {format_number(errors_per_kloc, 1)}")

    if failures > 0:
        error_cost_cursor = conn.execute(f"""
            SELECT COALESCE(SUM(t.cost), 0) as error_turn_cost
            FROM turns t
            WHERE EXISTS (
                SELECT 1 FROM tool_calls tc
                WHERE tc.turn_id = t.id AND tc.success = 0
            )
            AND 1=1 {date_filter}
        """, params)
        error_cost_row = error_cost_cursor.fetchone()
        error_cost = error_cost_row['error_turn_cost'] or 0
        lines.append(f"Error turn cost:      {colorize(format_currency(error_cost), Colors.RED, color_enabled)}")

    lines.append("")
    lines.append(bold("Time Efficiency", color_enabled))
    lines.append("-" * 40)

    if duration > 0:
        lines.append(f"Total active time:    {format_duration(duration)}")
        if sessions > 0:
            avg_session = duration / sessions
            lines.append(f"Avg session length:   {format_duration(int(avg_session))}")
        if loc_written > 0:
            loc_per_hour = loc_written / (duration / 3600)
            lines.append(f"LOC per hour:         {format_number(loc_per_hour, 1)}")

    return '\n'.join(lines)
