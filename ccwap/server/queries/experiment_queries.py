"""Experiment tag query module with smart tag support."""

from typing import Optional, List, Dict, Any

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter


async def _resolve_tag_sessions(
    db: aiosqlite.Connection, tag_name: str
) -> List[str]:
    """
    Resolve all session IDs for a tag by:
    1. Evaluating criteria from tag_definitions (dynamic/smart)
    2. UNIONing with explicit entries from experiment_tags (manual)
    3. Deduplicating
    """
    session_ids: set = set()

    # Step 1: Check tag_definitions for dynamic criteria
    cursor = await db.execute(
        "SELECT * FROM tag_definitions WHERE tag_name = ?", (tag_name,)
    )
    defn = await cursor.fetchone()

    if defn:
        params: list = []
        filters: list = []

        # Date range
        if defn[2]:  # date_from
            filters.append("date(s.first_timestamp, 'localtime') >= ?")
            params.append(defn[2])
        if defn[3]:  # date_to
            filters.append("date(s.first_timestamp, 'localtime') <= ?")
            params.append(defn[3])

        # Project path (LIKE match)
        if defn[4]:  # project_path
            filters.append(
                "(s.project_path LIKE ? OR s.project_display LIKE ?)"
            )
            params.extend([f"%{defn[4]}%", f"%{defn[4]}%"])

        # CC version
        if defn[5]:  # cc_version
            filters.append("s.cc_version LIKE ?")
            params.append(f"%{defn[5]}%")

        where_clause = " AND ".join(filters) if filters else "1=1"
        query = f"""
            SELECT s.session_id FROM sessions s
            WHERE s.first_timestamp IS NOT NULL AND {where_clause}
        """

        # Model filter (subquery into turns)
        if defn[6]:  # model
            query += " AND s.session_id IN (SELECT DISTINCT session_id FROM turns WHERE model LIKE ?)"
            params.append(f"%{defn[6]}%")

        # Cost range (subqueries into turns)
        if defn[7] is not None:  # min_cost
            query += " AND s.session_id IN (SELECT session_id FROM turns GROUP BY session_id HAVING SUM(cost) >= ?)"
            params.append(defn[7])
        if defn[8] is not None:  # max_cost
            query += " AND s.session_id IN (SELECT session_id FROM turns GROUP BY session_id HAVING SUM(cost) <= ?)"
            params.append(defn[8])

        # LOC range (subqueries into tool_calls)
        if defn[9] is not None:  # min_loc
            query += " AND s.session_id IN (SELECT session_id FROM tool_calls GROUP BY session_id HAVING SUM(loc_written) >= ?)"
            params.append(defn[9])
        if defn[10] is not None:  # max_loc
            query += " AND s.session_id IN (SELECT session_id FROM tool_calls GROUP BY session_id HAVING SUM(loc_written) <= ?)"
            params.append(defn[10])

        cursor = await db.execute(query, params)
        rows = await cursor.fetchall()
        session_ids.update(r[0] for r in rows)

    # Step 2: Add explicit manual session IDs from experiment_tags
    cursor = await db.execute(
        "SELECT session_id FROM experiment_tags WHERE tag_name = ?",
        (tag_name,),
    )
    rows = await cursor.fetchall()
    session_ids.update(r[0] for r in rows)

    return list(session_ids)


async def get_tags(db: aiosqlite.Connection) -> List[Dict[str, Any]]:
    """Get all experiment tags with session counts (smart + manual)."""
    # Collect all distinct tag names from both tables
    cursor = await db.execute("""
        SELECT tag_name, created_at FROM tag_definitions
        UNION
        SELECT DISTINCT tag_name, MIN(created_at) FROM experiment_tags GROUP BY tag_name
    """)
    rows = await cursor.fetchall()

    seen: set = set()
    results: list = []
    for row in rows:
        name = row[0]
        if name in seen:
            continue
        seen.add(name)

        sessions = await _resolve_tag_sessions(db, name)

        # Check if smart tag
        cursor2 = await db.execute(
            "SELECT description, date_from, date_to, project_path, cc_version, model, min_cost, max_cost, min_loc, max_loc FROM tag_definitions WHERE tag_name = ?",
            (name,),
        )
        defn_row = await cursor2.fetchone()

        tag_info: Dict[str, Any] = {
            "tag_name": name,
            "session_count": len(sessions),
            "created_at": row[1],
            "is_smart": defn_row is not None,
        }
        if defn_row:
            tag_info["criteria"] = {
                "description": defn_row[0],
                "date_from": defn_row[1],
                "date_to": defn_row[2],
                "project_path": defn_row[3],
                "cc_version": defn_row[4],
                "model": defn_row[5],
                "min_cost": defn_row[6],
                "max_cost": defn_row[7],
                "min_loc": defn_row[8],
                "max_loc": defn_row[9],
            }
        results.append(tag_info)

    results.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return results


async def create_tag(
    db: aiosqlite.Connection,
    tag_name: str,
    session_ids: Optional[List[str]] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    project_path: Optional[str] = None,
    cc_version: Optional[str] = None,
    model: Optional[str] = None,
    min_cost: Optional[float] = None,
    max_cost: Optional[float] = None,
    min_loc: Optional[int] = None,
    max_loc: Optional[int] = None,
    description: Optional[str] = None,
) -> int:
    """
    Create/assign experiment tags to sessions.

    Smart mode: if any criteria fields are provided, stores them in
    tag_definitions for dynamic evaluation.
    Manual mode: if only session_ids are provided, inserts into
    experiment_tags (static).
    """
    has_criteria = any([
        date_from, date_to, project_path, cc_version, model,
        min_cost is not None, max_cost is not None,
        min_loc is not None, max_loc is not None,
    ])

    if session_ids and not has_criteria:
        # Pure manual mode -- same as before
        tagged = 0
        for sid in session_ids:
            try:
                await db.execute(
                    "INSERT OR IGNORE INTO experiment_tags (tag_name, session_id) VALUES (?, ?)",
                    (tag_name, sid),
                )
                tagged += 1
            except Exception:
                pass
        await db.commit()
        return tagged

    if has_criteria:
        # Smart tag mode -- store criteria in tag_definitions
        await db.execute(
            """INSERT OR REPLACE INTO tag_definitions
                (tag_name, description, date_from, date_to, project_path,
                 cc_version, model, min_cost, max_cost, min_loc, max_loc)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                tag_name, description, date_from, date_to, project_path,
                cc_version, model, min_cost, max_cost, min_loc, max_loc,
            ),
        )

        # Also add any explicit session_ids if provided alongside criteria
        if session_ids:
            for sid in session_ids:
                try:
                    await db.execute(
                        "INSERT OR IGNORE INTO experiment_tags (tag_name, session_id) VALUES (?, ?)",
                        (tag_name, sid),
                    )
                except Exception:
                    pass

        await db.commit()
        sessions = await _resolve_tag_sessions(db, tag_name)
        return len(sessions)

    # Fallback: no criteria, no session_ids -- empty tag definition
    await db.execute(
        "INSERT OR REPLACE INTO tag_definitions (tag_name, description) VALUES (?, ?)",
        (tag_name, description),
    )
    await db.commit()
    return 0


async def delete_tag(db: aiosqlite.Connection, tag_name: str) -> int:
    """Delete all instances of a tag from both tables."""
    cursor = await db.execute(
        "DELETE FROM experiment_tags WHERE tag_name = ?", (tag_name,)
    )
    count = cursor.rowcount
    cursor2 = await db.execute(
        "DELETE FROM tag_definitions WHERE tag_name = ?", (tag_name,)
    )
    count += cursor2.rowcount
    await db.commit()
    return count


async def get_tag_criteria(
    db: aiosqlite.Connection, tag_name: str
) -> Dict[str, Any]:
    """Get the stored criteria for a tag."""
    cursor = await db.execute(
        "SELECT description, date_from, date_to, project_path, cc_version, model, min_cost, max_cost, min_loc, max_loc FROM tag_definitions WHERE tag_name = ?",
        (tag_name,),
    )
    row = await cursor.fetchone()
    if not row:
        return {"tag_name": tag_name, "is_smart": False, "criteria": None}
    return {
        "tag_name": tag_name,
        "is_smart": True,
        "criteria": {
            "description": row[0],
            "date_from": row[1],
            "date_to": row[2],
            "project_path": row[3],
            "cc_version": row[4],
            "model": row[5],
            "min_cost": row[6],
            "max_cost": row[7],
            "min_loc": row[8],
            "max_loc": row[9],
        },
    }


async def _get_expanded_metrics(
    db: aiosqlite.Connection, session_ids: List[str]
) -> Dict[str, Any]:
    """
    Get all 16 metrics for a set of session IDs.
    Uses two-query pattern (turns + tool_calls) to avoid cross-product.
    """
    if not session_ids:
        return {
            "sessions": 0, "cost": 0.0, "messages": 0, "user_turns": 0,
            "input_tokens": 0, "output_tokens": 0,
            "cache_read_tokens": 0, "cache_write_tokens": 0,
            "thinking_chars": 0, "tool_calls": 0, "errors": 0,
            "error_rate": 0.0, "loc_written": 0, "loc_delivered": 0,
            "files_created": 0, "files_edited": 0, "agent_spawns": 0,
            "cache_hit_rate": 0.0, "cost_per_kloc": 0.0,
            "tokens_per_loc": 0.0,
        }

    placeholders = ",".join("?" for _ in session_ids)

    # Query 1: Turn aggregates
    cursor = await db.execute(f"""
        SELECT
            COUNT(DISTINCT session_id) as sessions,
            SUM(cost) as cost,
            COUNT(*) as messages,
            COUNT(CASE WHEN entry_type = 'user' THEN 1 END) as user_turns,
            SUM(input_tokens) as input_tokens,
            SUM(output_tokens) as output_tokens,
            SUM(cache_read_tokens) as cache_read_tokens,
            SUM(cache_write_tokens) as cache_write_tokens,
            SUM(thinking_chars) as thinking_chars
        FROM turns
        WHERE session_id IN ({placeholders})
    """, session_ids)
    t_row = await cursor.fetchone()

    # Query 2: Tool call aggregates
    cursor = await db.execute(f"""
        SELECT
            COUNT(*) as tool_calls,
            SUM(CASE WHEN success = 0 THEN 1 ELSE 0 END) as errors,
            SUM(loc_written) as loc_written,
            SUM(lines_added) as lines_added,
            SUM(lines_deleted) as lines_deleted,
            COUNT(DISTINCT CASE WHEN tool_name = 'Write' THEN file_path END) as files_created,
            COUNT(DISTINCT CASE WHEN tool_name = 'Edit' THEN file_path END) as files_edited
        FROM tool_calls
        WHERE session_id IN ({placeholders})
    """, session_ids)
    tc_row = await cursor.fetchone()

    # Query 3: Agent spawns (sessions where is_agent=1)
    cursor = await db.execute(f"""
        SELECT COUNT(*) as agent_spawns
        FROM sessions
        WHERE session_id IN ({placeholders}) AND is_agent = 1
    """, session_ids)
    ag_row = await cursor.fetchone()

    sessions = t_row[0] or 0
    cost = t_row[1] or 0.0
    input_tokens = t_row[4] or 0
    output_tokens = t_row[5] or 0
    cache_read = t_row[6] or 0
    tool_calls = tc_row[0] or 0
    errors = tc_row[1] or 0
    loc_written = tc_row[2] or 0
    lines_added = tc_row[3] or 0
    lines_deleted = tc_row[4] or 0

    # Derived metrics
    error_rate = errors / tool_calls if tool_calls > 0 else 0.0
    loc_delivered = lines_added - lines_deleted
    cache_denom = input_tokens + cache_read
    cache_hit_rate = cache_read / cache_denom if cache_denom > 0 else 0.0
    cost_per_kloc = (cost / (loc_written / 1000)) if loc_written > 0 else 0.0
    tokens_per_loc = (input_tokens + output_tokens) / loc_written if loc_written > 0 else 0.0

    return {
        "sessions": sessions,
        "cost": cost,
        "messages": t_row[2] or 0,
        "user_turns": t_row[3] or 0,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read,
        "cache_write_tokens": t_row[7] or 0,
        "thinking_chars": t_row[8] or 0,
        "tool_calls": tool_calls,
        "errors": errors,
        "error_rate": error_rate,
        "loc_written": loc_written,
        "loc_delivered": loc_delivered,
        "files_created": tc_row[5] or 0,
        "files_edited": tc_row[6] or 0,
        "agent_spawns": ag_row[0] or 0,
        "cache_hit_rate": cache_hit_rate,
        "cost_per_kloc": cost_per_kloc,
        "tokens_per_loc": tokens_per_loc,
    }


async def compare_tags_multi(
    db: aiosqlite.Connection,
    tag_names: List[str],
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Compare 2-4 tags across expanded metrics."""

    async def _get_tag_summary(tag_name: str) -> Dict[str, Any]:
        session_ids = await _resolve_tag_sessions(db, tag_name)

        if not session_ids:
            return {
                "tag_name": tag_name,
                "sessions": 0, "cost": 0.0, "loc": 0, "loc_delivered": 0,
                "turns": 0, "error_rate": 0.0, "cache_hit_rate": 0.0,
                "cost_per_kloc": 0.0, "tokens_per_loc": 0.0,
                "thinking_chars": 0, "agent_spawns": 0,
                "files_created": 0, "files_edited": 0,
                "input_tokens": 0, "output_tokens": 0,
            }

        # Apply optional date filters on resolved sessions
        if date_from or date_to:
            placeholders = ",".join("?" for _ in session_ids)
            params: list = list(session_ids)
            date_filters = build_date_filter(
                "s.first_timestamp", date_from, date_to, params
            )
            cursor = await db.execute(f"""
                SELECT s.session_id FROM sessions s
                WHERE s.session_id IN ({placeholders}) {date_filters}
            """, params)
            filtered = await cursor.fetchall()
            session_ids = [r[0] for r in filtered]

        if not session_ids:
            return {
                "tag_name": tag_name,
                "sessions": 0, "cost": 0.0, "loc": 0, "loc_delivered": 0,
                "turns": 0, "error_rate": 0.0, "cache_hit_rate": 0.0,
                "cost_per_kloc": 0.0, "tokens_per_loc": 0.0,
                "thinking_chars": 0, "agent_spawns": 0,
                "files_created": 0, "files_edited": 0,
                "input_tokens": 0, "output_tokens": 0,
            }

        metrics = await _get_expanded_metrics(db, session_ids)
        return {
            "tag_name": tag_name,
            "sessions": metrics["sessions"],
            "cost": metrics["cost"],
            "loc": metrics["loc_written"],
            "loc_delivered": metrics["loc_delivered"],
            "turns": metrics["messages"],
            "error_rate": metrics["error_rate"],
            "cache_hit_rate": metrics["cache_hit_rate"],
            "cost_per_kloc": metrics["cost_per_kloc"],
            "tokens_per_loc": metrics["tokens_per_loc"],
            "thinking_chars": metrics["thinking_chars"],
            "agent_spawns": metrics["agent_spawns"],
            "files_created": metrics["files_created"],
            "files_edited": metrics["files_edited"],
            "input_tokens": metrics["input_tokens"],
            "output_tokens": metrics["output_tokens"],
        }

    results = []
    for tag in tag_names:
        summary = await _get_tag_summary(tag)
        results.append(summary)
    return results


async def get_tag_sessions(
    db: aiosqlite.Connection,
    tag_name: str,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Get sessions belonging to a specific tag (dynamic resolution)."""
    session_ids = await _resolve_tag_sessions(db, tag_name)

    if not session_ids:
        return []

    placeholders = ",".join("?" for _ in session_ids)

    # Apply date filters
    params: list = list(session_ids)
    date_filters = build_date_filter(
        "s.first_timestamp", date_from, date_to, params
    )

    cursor = await db.execute(f"""
        SELECT
            s.session_id,
            s.project_display,
            s.first_timestamp,
            s.git_branch
        FROM sessions s
        WHERE s.session_id IN ({placeholders}) {date_filters}
        ORDER BY s.first_timestamp DESC
    """, params)
    session_rows = await cursor.fetchall()

    if not session_rows:
        return []

    result = []
    for srow in session_rows:
        sid = srow[0]
        cursor = await db.execute("""
            SELECT SUM(cost) as total_cost, COUNT(*) as turn_count,
                   MAX(CASE WHEN model IS NOT NULL AND model NOT LIKE '<%' THEN model END) as model_default
            FROM turns
            WHERE session_id = ?
        """, (sid,))
        t_row = await cursor.fetchone()

        result.append({
            "session_id": sid,
            "project_display": srow[1] or sid,
            "start_time": srow[2],
            "total_cost": t_row[0] or 0.0,
            "turn_count": t_row[1] or 0,
            "model_default": t_row[2],
        })

    return result


async def compare_tags(
    db: aiosqlite.Connection,
    tag_a: str,
    tag_b: str,
) -> Dict[str, Any]:
    """Compare two experiment tags with expanded 16 metrics in categories."""
    sessions_a = await _resolve_tag_sessions(db, tag_a)
    sessions_b = await _resolve_tag_sessions(db, tag_b)

    metrics_a = await _get_expanded_metrics(db, sessions_a)
    metrics_b = await _get_expanded_metrics(db, sessions_b)

    # Metric definitions: (name, category, higher_is_better)
    metric_defs = [
        # Cost & Efficiency
        ("cost", "cost", False),
        ("cost_per_kloc", "cost", False),
        ("cache_hit_rate", "cost", True),
        # Productivity
        ("loc_written", "productivity", True),
        ("loc_delivered", "productivity", True),
        ("files_created", "productivity", True),
        ("files_edited", "productivity", True),
        # Tokens
        ("input_tokens", "tokens", False),
        ("output_tokens", "tokens", True),
        ("tokens_per_loc", "tokens", False),
        ("thinking_chars", "tokens", True),
        # Quality & Workflow
        ("sessions", "quality", True),
        ("user_turns", "quality", True),
        ("tool_calls", "quality", True),
        ("error_rate", "quality", False),
        ("agent_spawns", "quality", True),
    ]

    comparisons = []
    for metric_name, category, higher_is_better in metric_defs:
        a_val = metrics_a.get(metric_name, 0)
        b_val = metrics_b.get(metric_name, 0)
        delta = b_val - a_val
        pct = (delta / a_val * 100) if a_val != 0 else 0

        if higher_is_better:
            is_improvement = delta > 0
        else:
            is_improvement = delta < 0

        comparisons.append({
            "metric_name": metric_name,
            "category": category,
            "tag_a_value": a_val,
            "tag_b_value": b_val,
            "absolute_delta": delta,
            "percentage_delta": pct,
            "is_improvement": is_improvement,
        })

    return {
        "tag_a": tag_a,
        "tag_b": tag_b,
        "tag_a_sessions": metrics_a["sessions"],
        "tag_b_sessions": metrics_b["sessions"],
        "metrics": comparisons,
    }
