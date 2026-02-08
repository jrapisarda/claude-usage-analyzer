"""
Cost breakdown report for CCWAP.

Generates the --cost-breakdown view with per-token-type cost analysis.
"""

import sqlite3
from datetime import datetime, timedelta
from typing import Dict, Any, Optional, List

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, bold, colorize, Colors, create_bar
)
from ccwap.cost.pricing import get_pricing_for_model


def generate_cost_breakdown(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate cost breakdown report by token type.

    Shows per-token-type cost analysis, cache savings, project breakdown,
    and cost efficiency metrics.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("COST BREAKDOWN BY TOKEN TYPE", color_enabled))

    if date_from and date_to:
        lines.append(f"({date_from.strftime('%Y-%m-%d')} to {date_to.strftime('%Y-%m-%d')})")
    lines.append("")

    # Build date filter
    date_filter = ""
    params: List[str] = []
    if date_from:
        date_filter += " AND date(timestamp) >= date(?)"
        params.append(date_from.strftime('%Y-%m-%d'))
    if date_to:
        date_filter += " AND date(timestamp) <= date(?)"
        params.append(date_to.strftime('%Y-%m-%d'))

    # Query turns grouped by model to compute per-type costs with correct pricing
    cursor = conn.execute(f"""
        SELECT
            model,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(cache_write_tokens) as cache_write_tokens,
            SUM(cost) as cost
        FROM turns
        WHERE 1=1 {date_filter}
        GROUP BY model
    """, params)

    model_rows = cursor.fetchall()

    if not model_rows:
        return lines[0] + "\n\nNo data found."

    # Aggregate costs by token type across all models
    total_input_cost = 0.0
    total_output_cost = 0.0
    total_cache_read_cost = 0.0
    total_cache_write_cost = 0.0
    total_input_tokens = 0
    total_output_tokens = 0
    total_cache_read_tokens = 0
    total_cache_write_tokens = 0

    for r in model_rows:
        model = r['model']
        pricing = get_pricing_for_model(model, config)

        input_tokens = r['input_tokens'] or 0
        output_tokens = r['output_tokens'] or 0
        cache_read_tokens = r['cache_read_tokens'] or 0
        cache_write_tokens = r['cache_write_tokens'] or 0

        total_input_cost += (input_tokens / 1_000_000) * pricing['input']
        total_output_cost += (output_tokens / 1_000_000) * pricing['output']
        total_cache_read_cost += (cache_read_tokens / 1_000_000) * pricing['cache_read']
        total_cache_write_cost += (cache_write_tokens / 1_000_000) * pricing['cache_write']

        total_input_tokens += input_tokens
        total_output_tokens += output_tokens
        total_cache_read_tokens += cache_read_tokens
        total_cache_write_tokens += cache_write_tokens

    grand_total_cost = (
        total_input_cost + total_output_cost
        + total_cache_read_cost + total_cache_write_cost
    )

    # --- Section 1: Overall Cost Breakdown ---
    lines.append(bold("OVERALL COST BREAKDOWN", color_enabled))
    lines.append("-" * 40)

    type_data = [
        ("Input", total_input_cost, total_input_tokens),
        ("Output", total_output_cost, total_output_tokens),
        ("Cache Read", total_cache_read_cost, total_cache_read_tokens),
        ("Cache Write", total_cache_write_cost, total_cache_write_tokens),
    ]

    max_type_cost = max(cost for _, cost, _ in type_data) if grand_total_cost > 0 else 0

    headers = ['Token Type', 'Cost', '% of Total', 'Tokens', 'Bar']
    alignments = ['l', 'r', 'r', 'r', 'l']
    table_rows = []

    for type_name, cost, tokens in type_data:
        pct = (cost / grand_total_cost * 100) if grand_total_cost > 0 else 0
        bar = create_bar(cost, max_type_cost, width=15)
        table_rows.append([
            type_name,
            format_currency(cost),
            format_percentage(pct),
            format_tokens(tokens),
            bar,
        ])

    # Totals row
    total_all_tokens = (
        total_input_tokens + total_output_tokens
        + total_cache_read_tokens + total_cache_write_tokens
    )
    table_rows.append([
        bold('TOTAL', color_enabled),
        bold(format_currency(grand_total_cost), color_enabled),
        bold('100.0%', color_enabled),
        bold(format_tokens(total_all_tokens), color_enabled),
        '',
    ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))
    lines.append("")

    # --- Section 2: Cost by Token Type Over Time (last 14 days) ---
    lines.append(bold("COST BY TOKEN TYPE OVER TIME", color_enabled))
    lines.append("(Last 14 days)")
    lines.append("")

    end_date = date_to if date_to else datetime.now()
    start_14 = end_date - timedelta(days=13)

    time_params: List[str] = [start_14.strftime('%Y-%m-%d'), end_date.strftime('%Y-%m-%d')]

    cursor = conn.execute("""
        SELECT
            date(timestamp) as date,
            model,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(cache_write_tokens) as cache_write_tokens
        FROM turns
        WHERE date(timestamp) >= date(?)
        AND date(timestamp) <= date(?)
        GROUP BY date(timestamp), model
        ORDER BY date ASC
    """, time_params)

    day_model_rows = cursor.fetchall()

    # Aggregate per day
    daily_costs: Dict[str, Dict[str, float]] = {}
    for r in day_model_rows:
        date_str = r['date']
        pricing = get_pricing_for_model(r['model'], config)

        if date_str not in daily_costs:
            daily_costs[date_str] = {
                'input': 0.0, 'output': 0.0,
                'cache_read': 0.0, 'cache_write': 0.0,
            }

        daily_costs[date_str]['input'] += (
            (r['input_tokens'] or 0) / 1_000_000
        ) * pricing['input']
        daily_costs[date_str]['output'] += (
            (r['output_tokens'] or 0) / 1_000_000
        ) * pricing['output']
        daily_costs[date_str]['cache_read'] += (
            (r['cache_read_tokens'] or 0) / 1_000_000
        ) * pricing['cache_read']
        daily_costs[date_str]['cache_write'] += (
            (r['cache_write_tokens'] or 0) / 1_000_000
        ) * pricing['cache_write']

    if daily_costs:
        time_headers = ['Date', 'Input$', 'Output$', 'Cache Read$', 'Cache Write$', 'Total$']
        time_alignments = ['l', 'r', 'r', 'r', 'r', 'r']
        time_rows = []

        sorted_dates = sorted(daily_costs.keys())
        for date_str in sorted_dates:
            dc = daily_costs[date_str]
            day_total = dc['input'] + dc['output'] + dc['cache_read'] + dc['cache_write']
            time_rows.append([
                date_str,
                format_currency(dc['input']),
                format_currency(dc['output']),
                format_currency(dc['cache_read']),
                format_currency(dc['cache_write']),
                format_currency(day_total),
            ])

        # Totals row
        sum_input = sum(dc['input'] for dc in daily_costs.values())
        sum_output = sum(dc['output'] for dc in daily_costs.values())
        sum_cache_read = sum(dc['cache_read'] for dc in daily_costs.values())
        sum_cache_write = sum(dc['cache_write'] for dc in daily_costs.values())
        sum_total = sum_input + sum_output + sum_cache_read + sum_cache_write

        time_rows.append([
            bold('TOTAL', color_enabled),
            bold(format_currency(sum_input), color_enabled),
            bold(format_currency(sum_output), color_enabled),
            bold(format_currency(sum_cache_read), color_enabled),
            bold(format_currency(sum_cache_write), color_enabled),
            bold(format_currency(sum_total), color_enabled),
        ])

        lines.append(format_table(time_headers, time_rows, time_alignments, color_enabled))
    else:
        lines.append("No data for the last 14 days.")

    lines.append("")

    # --- Section 3: Cache Savings Analysis ---
    lines.append(bold("CACHE SAVINGS ANALYSIS", color_enabled))
    lines.append("-" * 40)

    # Calculate what cache reads would cost at full input price
    full_input_cost_for_cache = 0.0
    for r in model_rows:
        model = r['model']
        pricing = get_pricing_for_model(model, config)
        cache_read_tokens = r['cache_read_tokens'] or 0
        full_input_cost_for_cache += (cache_read_tokens / 1_000_000) * pricing['input']

    cache_savings = full_input_cost_for_cache - total_cache_read_cost
    savings_pct = (cache_savings / full_input_cost_for_cache * 100) if full_input_cost_for_cache > 0 else 0

    lines.append(f"Cache Reads:           {format_tokens(total_cache_read_tokens)}")
    lines.append(f"Cache Read Cost:       {format_currency(total_cache_read_cost)}")
    lines.append(f"Full Input Cost:       {format_currency(full_input_cost_for_cache)}")

    savings_str = format_currency(cache_savings)
    if cache_savings > 0:
        savings_str = colorize(savings_str, Colors.GREEN, color_enabled)
    lines.append(f"Savings:               {savings_str}")

    savings_pct_str = format_percentage(savings_pct)
    if savings_pct > 50:
        savings_pct_str = colorize(savings_pct_str, Colors.GREEN, color_enabled)
    elif savings_pct > 20:
        savings_pct_str = colorize(savings_pct_str, Colors.YELLOW, color_enabled)
    lines.append(f"Savings %:             {savings_pct_str}")
    lines.append("")

    # --- Section 4: Cost Breakdown by Project ---
    lines.append(bold("COST BREAKDOWN BY PROJECT", color_enabled))
    lines.append("(Top 10 by cost)")
    lines.append("")

    project_params = params.copy()
    cursor = conn.execute(f"""
        SELECT
            s.project_display,
            t.model,
            SUM(t.input_tokens) as input_tokens,
            SUM(t.output_tokens) as output_tokens,
            SUM(t.cache_read_tokens) as cache_read_tokens,
            SUM(t.cache_write_tokens) as cache_write_tokens,
            SUM(t.cost) as cost
        FROM sessions s
        JOIN turns t ON t.session_id = s.session_id
        WHERE 1=1 {date_filter.replace('timestamp', 't.timestamp')}
        GROUP BY s.project_display, t.model
        ORDER BY s.project_display
    """, project_params)

    project_model_rows = cursor.fetchall()

    # Aggregate per project with per-model pricing
    project_costs: Dict[str, Dict[str, float]] = {}
    for r in project_model_rows:
        project = r['project_display'] or 'Unknown'
        pricing = get_pricing_for_model(r['model'], config)

        if project not in project_costs:
            project_costs[project] = {
                'input': 0.0, 'output': 0.0,
                'cache': 0.0, 'total': 0.0,
            }

        input_cost = ((r['input_tokens'] or 0) / 1_000_000) * pricing['input']
        output_cost = ((r['output_tokens'] or 0) / 1_000_000) * pricing['output']
        cache_cost = (
            ((r['cache_read_tokens'] or 0) / 1_000_000) * pricing['cache_read']
            + ((r['cache_write_tokens'] or 0) / 1_000_000) * pricing['cache_write']
        )
        total = input_cost + output_cost + cache_cost

        project_costs[project]['input'] += input_cost
        project_costs[project]['output'] += output_cost
        project_costs[project]['cache'] += cache_cost
        project_costs[project]['total'] += total

    # Sort by total cost and take top 10
    sorted_projects = sorted(
        project_costs.items(), key=lambda x: x[1]['total'], reverse=True
    )[:10]

    if sorted_projects:
        proj_headers = ['Project', 'Input$', 'Output$', 'Cache$', 'Total$', 'Output%']
        proj_alignments = ['l', 'r', 'r', 'r', 'r', 'r']
        proj_rows = []

        for project_name, costs in sorted_projects:
            display_name = project_name
            if len(display_name) > 35:
                display_name = display_name[:32] + '...'

            output_pct = (
                costs['output'] / costs['total'] * 100
            ) if costs['total'] > 0 else 0

            output_pct_str = format_percentage(output_pct)
            if output_pct > 70:
                output_pct_str = colorize(output_pct_str, Colors.YELLOW, color_enabled)

            proj_rows.append([
                display_name,
                format_currency(costs['input']),
                format_currency(costs['output']),
                format_currency(costs['cache']),
                format_currency(costs['total']),
                output_pct_str,
            ])

        # Totals row
        proj_total_input = sum(c['input'] for _, c in sorted_projects)
        proj_total_output = sum(c['output'] for _, c in sorted_projects)
        proj_total_cache = sum(c['cache'] for _, c in sorted_projects)
        proj_total_total = sum(c['total'] for _, c in sorted_projects)

        proj_rows.append([
            bold('TOTAL', color_enabled),
            bold(format_currency(proj_total_input), color_enabled),
            bold(format_currency(proj_total_output), color_enabled),
            bold(format_currency(proj_total_cache), color_enabled),
            bold(format_currency(proj_total_total), color_enabled),
            '',
        ])

        lines.append(format_table(proj_headers, proj_rows, proj_alignments, color_enabled))
    else:
        lines.append("No project data found.")

    lines.append("")

    # --- Section 5: Cost Efficiency Metrics ---
    lines.append(bold("COST EFFICIENCY METRICS", color_enabled))
    lines.append("-" * 40)

    # Avg cost per turn
    cursor = conn.execute(f"""
        SELECT
            COUNT(*) as turn_count,
            SUM(cost) as total_cost
        FROM turns
        WHERE 1=1 {date_filter}
    """, params)

    turn_stats = cursor.fetchone()
    turn_count = turn_stats['turn_count'] or 0
    total_cost = turn_stats['total_cost'] or 0

    if turn_count > 0:
        avg_cost_per_turn = total_cost / turn_count
        lines.append(f"Avg cost per turn:     {format_currency(avg_cost_per_turn)}")

    # Daily cost stats
    cursor = conn.execute(f"""
        SELECT
            date(timestamp) as date,
            SUM(cost) as daily_cost
        FROM turns
        WHERE 1=1 {date_filter}
        GROUP BY date(timestamp)
        ORDER BY daily_cost ASC
    """, params)

    daily_rows = cursor.fetchall()

    if daily_rows:
        daily_cost_values = [r['daily_cost'] or 0 for r in daily_rows]
        num_days = len(daily_cost_values)

        # Median daily cost
        sorted_costs = sorted(daily_cost_values)
        if num_days % 2 == 1:
            median_cost = sorted_costs[num_days // 2]
        else:
            median_cost = (sorted_costs[num_days // 2 - 1] + sorted_costs[num_days // 2]) / 2
        lines.append(f"Median daily cost:     {format_currency(median_cost)}")

        # Daily average
        daily_avg = sum(daily_cost_values) / num_days
        lines.append(f"Daily average:         {format_currency(daily_avg)}")

        # Most expensive day
        most_expensive = max(daily_rows, key=lambda r: r['daily_cost'] or 0)
        most_exp_str = colorize(
            format_currency(most_expensive['daily_cost'] or 0),
            Colors.YELLOW, color_enabled
        )
        lines.append(f"Most expensive day:    {most_expensive['date']} ({most_exp_str})")

        # Cheapest day
        cheapest = min(daily_rows, key=lambda r: r['daily_cost'] or 0)
        cheapest_str = colorize(
            format_currency(cheapest['daily_cost'] or 0),
            Colors.GREEN, color_enabled
        )
        lines.append(f"Cheapest day:          {cheapest['date']} ({cheapest_str})")

    return '\n'.join(lines)
