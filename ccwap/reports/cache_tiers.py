"""
Ephemeral cache tier analysis report for CCWAP.

Generates the --cache-tiers view analyzing cache tier usage patterns.
"""

import sqlite3
from datetime import datetime
from typing import Dict, Any, Optional

from ccwap.output.formatter import (
    format_number, format_percentage, format_tokens, format_currency,
    format_table, bold, colorize, Colors, create_bar
)


def generate_cache_tiers(
    conn: sqlite3.Connection,
    config: Dict[str, Any],
    date_from: Optional[datetime] = None,
    date_to: Optional[datetime] = None,
    color_enabled: bool = True
) -> str:
    """
    Generate ephemeral cache tier analysis report.

    Args:
        conn: Database connection
        config: Configuration dict
        date_from: Start date filter
        date_to: End date filter
        color_enabled: Whether to apply colors
    """
    lines = []
    lines.append(bold("EPHEMERAL CACHE TIER ANALYSIS", color_enabled))

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

    # ── CACHE OVERVIEW ────────────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            SUM(t.cache_write_tokens) as total_cache_write,
            SUM(t.cache_read_tokens) as total_cache_read,
            SUM(t.ephemeral_5m_tokens) as total_ephemeral_5m,
            SUM(t.ephemeral_1h_tokens) as total_ephemeral_1h,
            SUM(t.input_tokens) as total_input,
            SUM(t.cache_read_tokens) as total_cache_read_for_rate
        FROM turns t
        WHERE 1=1 {date_filter}
    """, params)

    summary = cursor.fetchone()

    total_cache_write = summary['total_cache_write'] or 0
    total_cache_read = summary['total_cache_read'] or 0
    total_ephemeral_5m = summary['total_ephemeral_5m'] or 0
    total_ephemeral_1h = summary['total_ephemeral_1h'] or 0
    total_input = summary['total_input'] or 0

    if total_cache_write == 0 and total_cache_read == 0 and total_ephemeral_5m == 0 and total_ephemeral_1h == 0:
        return lines[0] + "\n\nNo cache data found."

    cache_hit_denominator = total_input + total_cache_read
    cache_hit_rate = (total_cache_read / cache_hit_denominator * 100) if cache_hit_denominator > 0 else 0

    lines.append(bold("CACHE OVERVIEW", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Cache write tokens:   {format_tokens(total_cache_write)}")
    lines.append(f"Cache read tokens:    {format_tokens(total_cache_read)}")
    lines.append(f"Ephemeral 5m tokens:  {format_tokens(total_ephemeral_5m)}")
    lines.append(f"Ephemeral 1h tokens:  {format_tokens(total_ephemeral_1h)}")
    lines.append(f"Cache hit rate:       {format_percentage(cache_hit_rate)}")
    lines.append("")

    # ── CACHE TIER BREAKDOWN ──────────────────────────────────

    all_cache_tokens = total_cache_write + total_cache_read + total_ephemeral_5m + total_ephemeral_1h

    tier_data = [
        ('Persistent Write', total_cache_write),
        ('Persistent Read', total_cache_read),
        ('Ephemeral 5min', total_ephemeral_5m),
        ('Ephemeral 1hr', total_ephemeral_1h),
    ]

    max_tokens = max(tokens for _, tokens in tier_data)

    lines.append(bold("CACHE TIER BREAKDOWN", color_enabled))
    headers = ['Tier', 'Tokens', '% of All Cache', 'Bar']
    alignments = ['l', 'r', 'r', 'l']
    table_rows = []

    for tier_name, tokens in tier_data:
        pct = (tokens / all_cache_tokens * 100) if all_cache_tokens > 0 else 0
        bar = create_bar(tokens, max_tokens, width=15)

        table_rows.append([
            tier_name,
            format_tokens(tokens),
            format_percentage(pct, 1),
            bar,
        ])

    lines.append(format_table(headers, table_rows, alignments, color_enabled))
    lines.append("")

    # ── EPHEMERAL vs PERSISTENT CACHE ─────────────────────────

    ephemeral_total = total_ephemeral_5m + total_ephemeral_1h
    persistent_total = total_cache_read + total_cache_write
    combined_total = ephemeral_total + persistent_total

    ephemeral_pct = (ephemeral_total / combined_total * 100) if combined_total > 0 else 0
    persistent_pct = (persistent_total / combined_total * 100) if combined_total > 0 else 0

    lines.append(bold("EPHEMERAL vs PERSISTENT CACHE", color_enabled))
    lines.append("-" * 40)
    lines.append(f"Persistent (read+write): {format_tokens(persistent_total):>10}  "
                 f"{colorize(format_percentage(persistent_pct, 1), Colors.GREEN, color_enabled)}")
    lines.append(f"Ephemeral (5m+1h):       {format_tokens(ephemeral_total):>10}  "
                 f"{format_percentage(ephemeral_pct, 1)}")
    lines.append("")

    # ── CACHE TIERS BY MODEL ──────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            t.model,
            SUM(t.cache_read_tokens) as cache_read,
            SUM(t.cache_write_tokens) as cache_write,
            SUM(t.ephemeral_5m_tokens) as ephemeral_5m,
            SUM(t.ephemeral_1h_tokens) as ephemeral_1h,
            SUM(t.input_tokens) as input_tokens
        FROM turns t
        WHERE t.model IS NOT NULL {date_filter}
        GROUP BY t.model
        ORDER BY (COALESCE(SUM(t.cache_read_tokens), 0)
                + COALESCE(SUM(t.cache_write_tokens), 0)
                + COALESCE(SUM(t.ephemeral_5m_tokens), 0)
                + COALESCE(SUM(t.ephemeral_1h_tokens), 0)) DESC
    """, params)

    model_rows = cursor.fetchall()

    if model_rows:
        lines.append(bold("CACHE TIERS BY MODEL", color_enabled))
        headers = ['Model', 'Cache Read', 'Cache Write', 'Ephemeral 5m', 'Ephemeral 1h', 'Hit Rate']
        alignments = ['l', 'r', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in model_rows:
            model = r['model'] or 'Unknown'
            if len(model) > 30:
                model = model[:27] + '...'

            cache_read = r['cache_read'] or 0
            cache_write = r['cache_write'] or 0
            ephemeral_5m = r['ephemeral_5m'] or 0
            ephemeral_1h = r['ephemeral_1h'] or 0
            input_tokens = r['input_tokens'] or 0

            hit_denom = input_tokens + cache_read
            hit_rate = (cache_read / hit_denom * 100) if hit_denom > 0 else 0

            rate_str = format_percentage(hit_rate, 1)
            if hit_rate > 50:
                rate_str = colorize(rate_str, Colors.GREEN, color_enabled)
            elif hit_rate > 20:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)
            else:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)

            table_rows.append([
                model,
                format_tokens(cache_read),
                format_tokens(cache_write),
                format_tokens(ephemeral_5m),
                format_tokens(ephemeral_1h),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── CACHE TIERS BY PROJECT ────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            s.project_display,
            SUM(t.cache_read_tokens) as cache_read,
            SUM(t.cache_write_tokens) as cache_write,
            SUM(t.ephemeral_5m_tokens) as ephemeral_5m,
            SUM(t.ephemeral_1h_tokens) as ephemeral_1h,
            SUM(t.input_tokens) as input_tokens
        FROM turns t
        JOIN sessions s ON s.session_id = t.session_id
        WHERE 1=1 {date_filter}
        GROUP BY s.project_display
        ORDER BY (COALESCE(SUM(t.cache_read_tokens), 0)
                + COALESCE(SUM(t.cache_write_tokens), 0)
                + COALESCE(SUM(t.ephemeral_5m_tokens), 0)
                + COALESCE(SUM(t.ephemeral_1h_tokens), 0)) DESC
        LIMIT 10
    """, params)

    project_rows = cursor.fetchall()

    if project_rows:
        lines.append(bold("CACHE TIERS BY PROJECT (Top 10)", color_enabled))
        headers = ['Project', 'Cache Read', 'Cache Write', 'Ephemeral 5m', 'Ephemeral 1h', 'Hit Rate']
        alignments = ['l', 'r', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in project_rows:
            project = r['project_display'] or 'Unknown'
            if len(project) > 35:
                project = project[:32] + '...'

            cache_read = r['cache_read'] or 0
            cache_write = r['cache_write'] or 0
            ephemeral_5m = r['ephemeral_5m'] or 0
            ephemeral_1h = r['ephemeral_1h'] or 0
            input_tokens = r['input_tokens'] or 0

            hit_denom = input_tokens + cache_read
            hit_rate = (cache_read / hit_denom * 100) if hit_denom > 0 else 0

            rate_str = format_percentage(hit_rate, 1)
            if hit_rate > 50:
                rate_str = colorize(rate_str, Colors.GREEN, color_enabled)
            elif hit_rate > 20:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)
            else:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)

            table_rows.append([
                project,
                format_tokens(cache_read),
                format_tokens(cache_write),
                format_tokens(ephemeral_5m),
                format_tokens(ephemeral_1h),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))
        lines.append("")

    # ── DAILY CACHE TREND ─────────────────────────────────────

    cursor = conn.execute(f"""
        SELECT
            date(t.timestamp) as date,
            SUM(t.cache_read_tokens) as cache_read,
            SUM(t.cache_write_tokens) as cache_write,
            SUM(t.ephemeral_5m_tokens) as ephemeral_5m,
            SUM(t.ephemeral_1h_tokens) as ephemeral_1h,
            SUM(t.input_tokens) as input_tokens
        FROM turns t
        WHERE 1=1 {date_filter}
        GROUP BY date(t.timestamp)
        ORDER BY date DESC
        LIMIT 14
    """, params)

    daily_rows = cursor.fetchall()

    if daily_rows:
        lines.append(bold("DAILY CACHE TREND (Last 14 Days)", color_enabled))
        headers = ['Date', 'Cache Read', 'Cache Write', 'Ephemeral 5m', 'Ephemeral 1h', 'Hit Rate']
        alignments = ['l', 'r', 'r', 'r', 'r', 'r']
        table_rows = []

        for r in daily_rows:
            cache_read = r['cache_read'] or 0
            cache_write = r['cache_write'] or 0
            ephemeral_5m = r['ephemeral_5m'] or 0
            ephemeral_1h = r['ephemeral_1h'] or 0
            input_tokens = r['input_tokens'] or 0

            hit_denom = input_tokens + cache_read
            hit_rate = (cache_read / hit_denom * 100) if hit_denom > 0 else 0

            rate_str = format_percentage(hit_rate, 1)
            if hit_rate > 50:
                rate_str = colorize(rate_str, Colors.GREEN, color_enabled)
            elif hit_rate > 20:
                rate_str = colorize(rate_str, Colors.YELLOW, color_enabled)
            else:
                rate_str = colorize(rate_str, Colors.RED, color_enabled)

            table_rows.append([
                r['date'],
                format_tokens(cache_read),
                format_tokens(cache_write),
                format_tokens(ephemeral_5m),
                format_tokens(ephemeral_1h),
                rate_str,
            ])

        lines.append(format_table(headers, table_rows, alignments, color_enabled))

    return '\n'.join(lines)
