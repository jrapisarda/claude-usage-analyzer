"""
Model comparison report for CCWAP.

Generates the --models view with per-model analytics.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, bold, colorize, Colors, create_bar
)


def _shorten_model_name(model_name: str) -> str:
    """Shorten a model name for display."""
    return (
        model_name
        .replace('claude-', '')
        .replace('-20251101', '')
        .replace('-20250514', '')
        .replace('-20241022', '')
        .replace('-20250929', '')
    )


def generate_models(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate model comparison report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("MODEL COMPARISON", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build date filter
    date_filter = ""
    params = []
    if date_from:
        date_filter += " AND date(t.timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(t.timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # ── Section 1: Model Usage Overview ──────────────────────────
    cursor = conn.execute(f"""
        SELECT
            t.model,
            COUNT(*) as turns,
            SUM(t.cost) as cost,
            SUM(t.input_tokens) as input_tokens,
            SUM(t.output_tokens) as output_tokens,
            SUM(t.cache_read_tokens) as cache_read,
            SUM(t.cache_write_tokens) as cache_write
        FROM turns t
        WHERE t.model IS NOT NULL {date_filter}
        GROUP BY t.model
        ORDER BY cost DESC
    """, params)

    rows = cursor.fetchall()

    if not rows:
        return lines[0] + "\n\nNo model data found."

    total_turns = sum(r['turns'] for r in rows)
    max_cost = max(r['cost'] or 0 for r in rows)

    lines.append(bold("MODEL USAGE OVERVIEW", color_enabled))
    lines.append("")

    headers = ['Model', 'Turns', '% of Turns', 'Total Cost', 'Avg Cost/Turn', 'Bar']
    alignments = ['l', 'r', 'r', 'r', 'r', 'l']
    table_rows = []

    for r in rows:
        model_name = r['model'] or 'unknown'
        display_name = _shorten_model_name(model_name)
        turns = r['turns']
        cost = r['cost'] or 0
        pct = (turns / total_turns * 100) if total_turns > 0 else 0
        avg_cost = (cost / turns) if turns > 0 else 0
        bar = create_bar(cost, max_cost, width=15)

        table_rows.append([
            display_name,
            format_number(turns),
            format_percentage(pct, 1),
            format_currency(cost),
            format_currency(avg_cost),
            bar,
        ])

    # Totals row
    total_cost = sum(r['cost'] or 0 for r in rows)
    avg_total = (total_cost / total_turns) if total_turns > 0 else 0

    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_number(total_turns), color_enabled),
        bold('100.0%', color_enabled),
        bold(format_currency(total_cost), color_enabled),
        bold(format_currency(avg_total), color_enabled),
        '',
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # ── Section 2: Token Breakdown by Model ──────────────────────
    lines.append("")
    lines.append(bold("TOKEN BREAKDOWN BY MODEL", color_enabled))
    lines.append("")

    headers = ['Model', 'Input Tokens', 'Output Tokens', 'Cache Read', 'Cache Write', 'Total Tokens']
    alignments = ['l', 'r', 'r', 'r', 'r', 'r']
    table_rows = []

    for r in rows:
        model_name = r['model'] or 'unknown'
        display_name = _shorten_model_name(model_name)
        input_tokens = r['input_tokens'] or 0
        output_tokens = r['output_tokens'] or 0
        cache_read = r['cache_read'] or 0
        cache_write = r['cache_write'] or 0
        total = input_tokens + output_tokens + cache_read + cache_write

        table_rows.append([
            display_name,
            format_tokens(input_tokens),
            format_tokens(output_tokens),
            format_tokens(cache_read),
            format_tokens(cache_write),
            format_tokens(total),
        ])

    # Totals row
    total_input = sum(r['input_tokens'] or 0 for r in rows)
    total_output = sum(r['output_tokens'] or 0 for r in rows)
    total_cache_read = sum(r['cache_read'] or 0 for r in rows)
    total_cache_write = sum(r['cache_write'] or 0 for r in rows)
    total_all = total_input + total_output + total_cache_read + total_cache_write

    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_tokens(total_input), color_enabled),
        bold(format_tokens(total_output), color_enabled),
        bold(format_tokens(total_cache_read), color_enabled),
        bold(format_tokens(total_cache_write), color_enabled),
        bold(format_tokens(total_all), color_enabled),
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))

    # ── Section 3: Efficiency by Model ───────────────────────────
    lines.append("")
    lines.append(bold("EFFICIENCY BY MODEL", color_enabled))
    lines.append("")

    # Query tool stats joined through turn_id to get per-model metrics
    cursor = conn.execute(f"""
        SELECT
            t.model,
            SUM(tc.loc_written) as loc_written,
            COUNT(tc.rowid) as tool_calls,
            SUM(CASE WHEN tc.success = 1 THEN 1 ELSE 0 END) as successes,
            SUM(t.cost) as cost,
            SUM(t.output_tokens) as output_tokens
        FROM turns t
        JOIN tool_calls tc ON tc.turn_id = t.rowid
        WHERE t.model IS NOT NULL {date_filter}
        GROUP BY t.model
        ORDER BY cost DESC
    """, params)

    eff_rows = cursor.fetchall()

    if eff_rows:
        headers = ['Model', 'Total LOC', 'Cost/KLOC', 'Tokens/LOC', 'Tool Success Rate']
        alignments = ['l', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in eff_rows:
            model_name = r['model'] or 'unknown'
            display_name = _shorten_model_name(model_name)
            loc = r['loc_written'] or 0
            cost = r['cost'] or 0
            output_tokens = r['output_tokens'] or 0
            tool_calls = r['tool_calls'] or 0
            successes = r['successes'] or 0

            cost_per_kloc = format_currency(cost / (loc / 1000)) if loc > 0 else '-'
            tokens_per_loc = format_number(output_tokens / loc, 1) if loc > 0 else '-'
            success_rate = (successes / tool_calls * 100) if tool_calls > 0 else 0

            success_str = format_percentage(success_rate, 1)
            if success_rate < 80:
                success_str = colorize(success_str, Colors.RED, color_enabled)
            elif success_rate < 90:
                success_str = colorize(success_str, Colors.YELLOW, color_enabled)

            table_rows.append([
                display_name,
                format_number(loc),
                cost_per_kloc,
                tokens_per_loc,
                success_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
    else:
        lines.append("No tool call data available.")

    # ── Section 4: Model Usage Trend (Last 14 Days) ──────────────
    lines.append("")
    lines.append(bold("MODEL USAGE TREND (LAST 14 DAYS)", color_enabled))
    lines.append("-" * 40)

    cursor = conn.execute(f"""
        SELECT
            date(t.timestamp) as date,
            t.model,
            SUM(t.cost) as cost,
            COUNT(*) as turns
        FROM turns t
        WHERE t.model IS NOT NULL
            AND date(t.timestamp) >= date('now', '-14 days')
            {date_filter}
        GROUP BY date(t.timestamp), t.model
        ORDER BY date(t.timestamp) DESC, cost DESC
    """, params)

    trend_rows = cursor.fetchall()

    if trend_rows:
        # Group by date
        daily_data: Dict[str, list] = {}
        for r in trend_rows:
            date_str = r['date']
            if date_str not in daily_data:
                daily_data[date_str] = []
            daily_data[date_str].append(r)

        for date_str in sorted(daily_data.keys(), reverse=True):
            day_rows = daily_data[date_str]
            day_total = sum(r['cost'] or 0 for r in day_rows)
            lines.append(f"  {date_str}  {format_currency(day_total):>10}")
            for r in day_rows:
                model_name = _shorten_model_name(r['model'] or 'unknown')
                cost = r['cost'] or 0
                turns = r['turns']
                lines.append(f"    {model_name:28} {format_currency(cost):>10}  ({turns} turns)")
    else:
        lines.append("No trend data available.")

    # ── Section 5: Cache Efficiency by Model ─────────────────────
    lines.append("")
    lines.append(bold("CACHE EFFICIENCY BY MODEL", color_enabled))
    lines.append("-" * 40)

    for r in rows:
        model_name = r['model'] or 'unknown'
        display_name = _shorten_model_name(model_name)
        input_tokens = r['input_tokens'] or 0
        cache_read = r['cache_read'] or 0
        total_input = input_tokens + cache_read

        if total_input > 0:
            hit_rate = cache_read / total_input * 100
        else:
            hit_rate = 0.0

        rate_str = format_percentage(hit_rate, 1)
        if hit_rate > 50:
            rate_str = colorize(rate_str, Colors.GREEN, color_enabled)
        elif hit_rate > 20:
            rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)
        else:
            rate_str = colorize(rate_str, Colors.RED, color_enabled)

        bar = create_bar(hit_rate, 100, width=15)
        lines.append(f"  {display_name:30} {rate_str:>12}  {bar}")

    return '\n'.join(lines)
