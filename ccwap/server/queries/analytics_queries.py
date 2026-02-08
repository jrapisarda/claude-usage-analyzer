"""Deep analytics query module."""

from typing import Optional, Dict, Any, List

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter, build_summary_filter


async def get_thinking_analysis(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Extended thinking analysis."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            SUM(thinking_chars) as total_thinking,
            AVG(CASE WHEN thinking_chars > 0 THEN thinking_chars END) as avg_thinking,
            SUM(CASE WHEN thinking_chars > 0 THEN 1 ELSE 0 END) as turns_with_thinking,
            COUNT(*) as total_turns
        FROM turns
        WHERE timestamp IS NOT NULL {filters}
    """, params)
    row = await cursor.fetchone()

    total = row[0] or 0
    avg = row[1] or 0
    with_thinking = row[2] or 0
    total_turns = row[3] or 0

    # By model
    cursor = await db.execute(f"""
        SELECT
            model,
            SUM(thinking_chars) as thinking_chars,
            AVG(CASE WHEN thinking_chars > 0 THEN thinking_chars END) as avg_thinking,
            COUNT(CASE WHEN thinking_chars > 0 THEN 1 END) as turns_with
        FROM turns
        WHERE model IS NOT NULL AND model NOT LIKE '<%' AND thinking_chars > 0 {filters}
        GROUP BY model
        ORDER BY thinking_chars DESC
    """, params)
    model_rows = await cursor.fetchall()

    by_model = [
        {
            "model": r[0],
            "thinking_chars": r[1] or 0,
            "avg_thinking": r[2] or 0,
            "turns_with_thinking": r[3] or 0,
        }
        for r in model_rows
    ]

    return {
        "total_thinking_chars": total,
        "avg_thinking_per_turn": avg,
        "turns_with_thinking": with_thinking,
        "total_turns": total_turns,
        "thinking_rate": with_thinking / total_turns if total_turns > 0 else 0,
        "by_model": by_model,
    }


async def get_truncation_analysis(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Truncation/stop reason breakdown."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            COALESCE(stop_reason, 'none') as stop_reason,
            COUNT(*) as count
        FROM turns
        WHERE entry_type = 'assistant' {filters}
        GROUP BY stop_reason
        ORDER BY count DESC
    """, params)
    rows = await cursor.fetchall()

    total_turns = sum(r[1] for r in rows)
    by_stop_reason = [
        {
            "stop_reason": r[0],
            "count": r[1],
            "percentage": (r[1] / total_turns * 100) if total_turns > 0 else 0,
        }
        for r in rows
    ]

    return {
        "total_turns": total_turns,
        "by_stop_reason": by_stop_reason,
    }


async def get_sidechain_analysis(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Sidechain/branching analysis."""
    params: list = []
    filters = build_date_filter("t.timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            COUNT(CASE WHEN t.is_sidechain = 1 THEN 1 END) as sidechains,
            COUNT(*) as total
        FROM turns t
        WHERE t.timestamp IS NOT NULL {filters}
    """, params)
    row = await cursor.fetchone()
    sidechains = row[0] or 0
    total = row[1] or 0

    # By project
    cursor = await db.execute(f"""
        SELECT
            s.project_display,
            COUNT(CASE WHEN t.is_sidechain = 1 THEN 1 END) as sidechains,
            COUNT(*) as total
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE t.timestamp IS NOT NULL {filters}
        GROUP BY s.project_path
        HAVING sidechains > 0
        ORDER BY sidechains DESC
        LIMIT 10
    """, params)
    proj_rows = await cursor.fetchall()

    return {
        "total_sidechains": sidechains,
        "sidechain_rate": sidechains / total if total > 0 else 0,
        "by_project": [
            {"project": r[0], "sidechains": r[1], "total_turns": r[2]}
            for r in proj_rows
        ],
    }


async def get_cache_tier_analysis(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Ephemeral cache tier analysis."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            SUM(ephemeral_5m_tokens),
            SUM(ephemeral_1h_tokens),
            SUM(cache_read_tokens)
        FROM turns
        WHERE timestamp IS NOT NULL {filters}
    """, params)
    row = await cursor.fetchone()

    return {
        "ephemeral_5m_tokens": row[0] or 0,
        "ephemeral_1h_tokens": row[1] or 0,
        "standard_cache_tokens": row[2] or 0,
        "by_date": [],
    }


async def get_branch_analytics(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Branch-aware analytics."""
    params: list = []
    filters = build_date_filter("s.first_timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            COALESCE(s.git_branch, 'unknown') as branch,
            COUNT(DISTINCT s.session_id) as sessions,
            SUM(t.cost) as cost,
            SUM(t.output_tokens) as output_tokens,
            COUNT(t.id) as turns
        FROM sessions s
        LEFT JOIN turns t ON s.session_id = t.session_id
        WHERE s.first_timestamp IS NOT NULL {filters}
        GROUP BY s.git_branch
        ORDER BY cost DESC
        LIMIT 20
    """, params)
    rows = await cursor.fetchall()

    return {
        "branches": [
            {
                "branch": r[0],
                "sessions": r[1] or 0,
                "cost": r[2] or 0.0,
                "output_tokens": r[3] or 0,
                "turns": r[4] or 0,
            }
            for r in rows
        ],
    }


async def get_version_impact(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """CC version impact analysis."""
    params: list = []
    filters = build_date_filter("s.first_timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            COALESCE(s.cc_version, 'unknown') as version,
            COUNT(DISTINCT s.session_id) as sessions,
            SUM(t.cost) as cost,
            AVG(t.cost) as avg_turn_cost,
            COUNT(t.id) as turns
        FROM sessions s
        LEFT JOIN turns t ON s.session_id = t.session_id
        WHERE s.first_timestamp IS NOT NULL {filters}
        GROUP BY s.cc_version
        ORDER BY version DESC
    """, params)
    rows = await cursor.fetchall()

    return {
        "versions": [
            {
                "version": r[0],
                "sessions": r[1] or 0,
                "cost": r[2] or 0.0,
                "avg_turn_cost": r[3] or 0.0,
                "turns": r[4] or 0,
            }
            for r in rows
        ],
    }


async def get_skills_agents(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Skills and agents analysis."""
    params: list = []
    filters = build_summary_filter(date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            SUM(agent_spawns) as agent_spawns,
            SUM(skill_invocations) as skills
        FROM daily_summaries
        WHERE 1=1 {filters}
    """, params)
    row = await cursor.fetchone()

    # Agent cost from sessions where is_agent = 1
    agent_params: list = []
    agent_date_filter = build_date_filter("t.timestamp", date_from, date_to, agent_params)

    cursor = await db.execute(f"""
        SELECT SUM(t.cost)
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE s.is_agent = 1 {agent_date_filter}
    """, agent_params)
    cost_row = await cursor.fetchone()

    return {
        "total_agent_spawns": row[0] or 0,
        "total_skill_invocations": row[1] or 0,
        "agent_cost": cost_row[0] or 0.0 if cost_row else 0.0,
        "by_date": [],
    }


async def get_thinking_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daily thinking chars by model for sparkline trend."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            date(timestamp, 'localtime') as date,
            model,
            SUM(thinking_chars) as thinking_chars
        FROM turns
        WHERE timestamp IS NOT NULL
          AND thinking_chars > 0
          AND model IS NOT NULL AND model NOT LIKE '<%'
          {filters}
        GROUP BY date(timestamp, 'localtime'), model
        ORDER BY date(timestamp, 'localtime'), model
    """, params)
    rows = await cursor.fetchall()
    return [{"date": r[0], "model": r[1], "thinking_chars": r[2] or 0} for r in rows]


async def get_cache_trend(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Daily cache tier breakdown for stacked area chart."""
    params: list = []
    filters = build_date_filter("timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            date(timestamp, 'localtime') as date,
            SUM(COALESCE(ephemeral_5m_tokens, 0)) as ephemeral_5m,
            SUM(COALESCE(ephemeral_1h_tokens, 0)) as ephemeral_1h,
            SUM(COALESCE(cache_read_tokens, 0)) as standard_cache
        FROM turns
        WHERE timestamp IS NOT NULL
          {filters}
        GROUP BY date(timestamp, 'localtime')
        ORDER BY date(timestamp, 'localtime')
    """, params)
    rows = await cursor.fetchall()
    return [{"date": r[0], "ephemeral_5m": r[1] or 0, "ephemeral_1h": r[2] or 0, "standard_cache": r[3] or 0} for r in rows]
