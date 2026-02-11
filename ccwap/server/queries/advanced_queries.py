"""Query helpers for advanced analytics dashboards."""

from collections import Counter, defaultdict
from statistics import mean, pstdev
from typing import Any, Dict, List, Optional

import aiosqlite

from ccwap.server.queries.date_helpers import build_date_filter


def _parse_csv(value: Optional[str]) -> Optional[List[str]]:
    if not value:
        return None
    vals = [v.strip() for v in value.split(",") if v.strip()]
    return vals if vals else None


def _build_branch_filter(branches: Optional[List[str]], params: list, alias: str = "s") -> str:
    if not branches:
        return ""
    placeholders = ", ".join("?" for _ in branches)
    params.extend(branches)
    return f" AND COALESCE({alias}.git_branch, 'unknown') IN ({placeholders})"


async def get_reliability_dashboard(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Get reliability metrics for failures, categories, and costs."""
    params: list = []
    date_filter = build_date_filter("tc.timestamp", date_from, date_to, params)

    cursor = await db.execute(f"""
        SELECT
            COUNT(*) as total_calls,
            SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END) as total_errors,
            COALESCE(SUM(CASE WHEN tc.success = 0 THEN t.cost ELSE 0 END), 0) as error_cost
        FROM tool_calls tc
        LEFT JOIN turns t ON tc.turn_id = t.id
        WHERE tc.timestamp IS NOT NULL {date_filter}
    """, params)
    row = await cursor.fetchone()
    total_calls = int(row[0] or 0)
    total_errors = int(row[1] or 0)
    error_cost = float(row[2] or 0)

    cursor = await db.execute(f"""
        SELECT
            COALESCE(tc.tool_name, 'unknown') as tool_name,
            COALESCE(tc.error_category, 'unknown') as error_category,
            COUNT(*) as errors,
            COALESCE(SUM(t.cost), 0) as error_cost
        FROM tool_calls tc
        JOIN sessions s ON tc.session_id = s.session_id
        LEFT JOIN turns t ON tc.turn_id = t.id
        WHERE tc.success = 0 {date_filter}
        GROUP BY tool_name, error_category
        ORDER BY errors DESC
        LIMIT 300
    """, params)
    heatmap_rows = await cursor.fetchall()

    cursor = await db.execute(f"""
        SELECT
            COALESCE(tc.tool_name, 'unknown') as label,
            COUNT(*) as cnt,
            COALESCE(SUM(t.cost), 0) as cost
        FROM tool_calls tc
        LEFT JOIN turns t ON tc.turn_id = t.id
        WHERE tc.success = 0 {date_filter}
        GROUP BY label
        ORDER BY cnt DESC
        LIMIT 15
    """, params)
    pareto_tools = await cursor.fetchall()

    cursor = await db.execute(f"""
        SELECT
            COALESCE(tc.command_name, '(none)') as label,
            COUNT(*) as cnt,
            COALESCE(SUM(t.cost), 0) as cost
        FROM tool_calls tc
        LEFT JOIN turns t ON tc.turn_id = t.id
        WHERE tc.success = 0 {date_filter}
        GROUP BY label
        ORDER BY cnt DESC
        LIMIT 15
    """, params)
    pareto_commands = await cursor.fetchall()

    cursor = await db.execute(f"""
        SELECT
            COALESCE(tc.language, 'unknown') as label,
            COUNT(*) as cnt,
            COALESCE(SUM(t.cost), 0) as cost
        FROM tool_calls tc
        LEFT JOIN turns t ON tc.turn_id = t.id
        WHERE tc.success = 0 {date_filter}
        GROUP BY label
        ORDER BY cnt DESC
        LIMIT 15
    """, params)
    pareto_languages = await cursor.fetchall()

    cursor = await db.execute(f"""
        SELECT
            COALESCE(s.git_branch, 'unknown') as branch,
            COUNT(*) as errors,
            COALESCE(SUM(t.cost), 0) as cost
        FROM tool_calls tc
        JOIN sessions s ON tc.session_id = s.session_id
        LEFT JOIN turns t ON tc.turn_id = t.id
        WHERE tc.success = 0 {date_filter}
        GROUP BY branch
        ORDER BY errors DESC
    """, params)
    by_branch_rows = await cursor.fetchall()

    cursor = await db.execute(f"""
        SELECT
            tc.session_id,
            COALESCE(s.git_branch, 'unknown') as branch,
            COALESCE(tc.tool_name, 'unknown') as tool_name,
            tc.success,
            COALESCE(t.cost, 0) as turn_cost
        FROM tool_calls tc
        JOIN sessions s ON tc.session_id = s.session_id
        LEFT JOIN turns t ON tc.turn_id = t.id
        WHERE tc.timestamp IS NOT NULL {date_filter}
        ORDER BY tc.session_id, tc.timestamp, tc.id
    """, params)
    workflow_rows = await cursor.fetchall()

    counters: Counter = Counter()
    costs: defaultdict = defaultdict(float)
    prev_tool_by_session: Dict[str, str] = {}
    for sess_id, branch, tool_name, success, turn_cost in workflow_rows:
        from_tool = prev_tool_by_session.get(sess_id, "START")
        prev_tool_by_session[sess_id] = tool_name
        if int(success or 0) == 0:
            key = (from_tool, tool_name, branch)
            counters[key] += 1
            costs[key] += float(turn_cost or 0)

    top_failing_workflows = []
    for (from_tool, to_tool, branch), failures in counters.most_common(20):
        top_failing_workflows.append({
            "workflow": f"{from_tool}->{to_tool}",
            "from_tool": from_tool,
            "to_tool": to_tool,
            "branch": branch,
            "failures": int(failures),
            "cost": round(float(costs[(from_tool, to_tool, branch)]), 6),
        })

    return {
        "summary": {
            "total_tool_calls": total_calls,
            "total_errors": total_errors,
            "error_rate": (total_errors / total_calls) if total_calls > 0 else 0.0,
            "error_cost": round(error_cost, 6),
        },
        "heatmap": [{
            "tool_name": str(r[0]),
            "error_category": str(r[1]),
            "errors": int(r[2] or 0),
            "error_cost": round(float(r[3] or 0), 6),
        } for r in heatmap_rows],
        "pareto_tools": [{"label": str(r[0]), "count": int(r[1] or 0), "cost": round(float(r[2] or 0), 6)} for r in pareto_tools],
        "pareto_commands": [{"label": str(r[0]), "count": int(r[1] or 0), "cost": round(float(r[2] or 0), 6)} for r in pareto_commands],
        "pareto_languages": [{"label": str(r[0]), "count": int(r[1] or 0), "cost": round(float(r[2] or 0), 6)} for r in pareto_languages],
        "by_branch": [{"branch": str(r[0]), "errors": int(r[1] or 0), "cost": round(float(r[2] or 0), 6)} for r in by_branch_rows],
        "top_failing_workflows": top_failing_workflows,
    }


async def get_branch_health_dashboard(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    branches_csv: Optional[str] = None,
) -> Dict[str, Any]:
    """Get branch quality/cost/productivity trend with anomaly markers."""
    branches = _parse_csv(branches_csv)
    turn_params: list = []
    turn_filter = build_date_filter("t.timestamp", date_from, date_to, turn_params)
    turn_filter += _build_branch_filter(branches, turn_params, alias="s")

    cursor = await db.execute(f"""
        SELECT
            date(t.timestamp, 'localtime') as date,
            COALESCE(s.git_branch, 'unknown') as branch,
            COALESCE(SUM(t.cost), 0) as cost,
            COALESCE(SUM(t.cache_read_tokens), 0) as cache_read_tokens,
            COALESCE(SUM(t.input_tokens), 0) as input_tokens
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE t.timestamp IS NOT NULL {turn_filter}
        GROUP BY date, branch
        ORDER BY date, branch
    """, turn_params)
    turn_rows = await cursor.fetchall()

    tc_params: list = []
    tc_filter = build_date_filter("tc.timestamp", date_from, date_to, tc_params)
    tc_filter += _build_branch_filter(branches, tc_params, alias="s")
    cursor = await db.execute(f"""
        SELECT
            date(tc.timestamp, 'localtime') as date,
            COALESCE(s.git_branch, 'unknown') as branch,
            COUNT(*) as tool_calls,
            COALESCE(SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END), 0) as errors,
            COALESCE(SUM(tc.loc_written), 0) as loc_written
        FROM tool_calls tc
        JOIN sessions s ON tc.session_id = s.session_id
        WHERE tc.timestamp IS NOT NULL {tc_filter}
        GROUP BY date, branch
        ORDER BY date, branch
    """, tc_params)
    tc_rows = await cursor.fetchall()

    trend_map: Dict[tuple, Dict[str, Any]] = {}
    for date, branch, cost, cache_read, input_tokens in turn_rows:
        denom = float((input_tokens or 0) + (cache_read or 0))
        trend_map[(date, branch)] = {
            "date": str(date),
            "branch": str(branch),
            "cost": round(float(cost or 0), 6),
            "errors": 0,
            "tool_calls": 0,
            "loc_written": 0,
            "cache_hit_rate": (float(cache_read or 0) / denom) if denom > 0 else 0.0,
        }
    for date, branch, tool_calls, errors, loc_written in tc_rows:
        key = (str(date), str(branch))
        if key not in trend_map:
            trend_map[key] = {
                "date": str(date),
                "branch": str(branch),
                "cost": 0.0,
                "errors": 0,
                "tool_calls": 0,
                "loc_written": 0,
                "cache_hit_rate": 0.0,
            }
        trend_map[key]["tool_calls"] = int(tool_calls or 0)
        trend_map[key]["errors"] = int(errors or 0)
        trend_map[key]["loc_written"] = int(loc_written or 0)

    trend = sorted(trend_map.values(), key=lambda x: (x["date"], x["branch"]))

    summary_by_branch: Dict[str, Dict[str, Any]] = defaultdict(lambda: {
        "branch": "unknown",
        "cost": 0.0,
        "errors": 0,
        "tool_calls": 0,
        "loc_written": 0,
        "_cache_weighted": 0.0,
        "_days": 0,
    })
    for row in trend:
        b = row["branch"]
        s = summary_by_branch[b]
        s["branch"] = b
        s["cost"] += float(row["cost"])
        s["errors"] += int(row["errors"])
        s["tool_calls"] += int(row["tool_calls"])
        s["loc_written"] += int(row["loc_written"])
        s["_cache_weighted"] += float(row["cache_hit_rate"])
        s["_days"] += 1

    branches_summary = []
    for s in summary_by_branch.values():
        days = max(int(s.pop("_days", 0)), 1)
        cache_weighted = float(s.pop("_cache_weighted", 0.0))
        s["cache_hit_rate"] = cache_weighted / days
        s["cost"] = round(float(s["cost"]), 6)
        branches_summary.append(s)
    branches_summary.sort(key=lambda x: x["cost"], reverse=True)

    anomalies = []
    by_branch_costs: Dict[str, List[Dict[str, Any]]] = defaultdict(list)
    for row in trend:
        by_branch_costs[row["branch"]].append(row)
    for branch, rows in by_branch_costs.items():
        costs = [float(r["cost"]) for r in rows]
        if len(costs) < 3:
            continue
        avg = mean(costs)
        sigma = pstdev(costs)
        if sigma <= 0:
            continue
        threshold = avg + (2.0 * sigma)
        for r in rows:
            if float(r["cost"]) > threshold:
                zscore = (float(r["cost"]) - avg) / sigma
                anomalies.append({
                    "date": r["date"],
                    "branch": branch,
                    "cost": round(float(r["cost"]), 6),
                    "zscore": round(float(zscore), 3),
                    "reason": "cost_spike",
                })
    anomalies.sort(key=lambda x: x["zscore"], reverse=True)

    return {
        "branches": branches_summary,
        "trend": trend,
        "anomalies": anomalies[:50],
    }


async def get_prompt_efficiency_dashboard(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Get prompt efficiency scatter/funnel/outlier data."""
    params: list = []
    date_filter = build_date_filter("s.first_timestamp", date_from, date_to, params)
    cursor = await db.execute(f"""
        SELECT
            s.session_id,
            COALESCE(s.project_display, s.project_path) as project,
            COALESCE(s.git_branch, 'unknown') as branch,
            COALESCE((
                SELECT t2.model FROM turns t2
                WHERE t2.session_id = s.session_id
                AND t2.model IS NOT NULL AND t2.model NOT LIKE '<%'
                ORDER BY t2.timestamp DESC
                LIMIT 1
            ), 'unknown') as model,
            COALESCE((SELECT SUM(t.cost) FROM turns t WHERE t.session_id = s.session_id), 0) as cost,
            COALESCE((SELECT SUM(t.thinking_chars) FROM turns t WHERE t.session_id = s.session_id), 0) as thinking_chars,
            COALESCE((SELECT SUM(t.input_tokens) FROM turns t WHERE t.session_id = s.session_id), 0) as input_tokens,
            COALESCE((SELECT SUM(t.output_tokens) FROM turns t WHERE t.session_id = s.session_id), 0) as output_tokens,
            COALESCE((SELECT SUM(t.cache_read_tokens) FROM turns t WHERE t.session_id = s.session_id), 0) as cache_read_tokens,
            COALESCE((SELECT SUM(tc.loc_written) FROM tool_calls tc WHERE tc.session_id = s.session_id), 0) as loc_written,
            COALESCE((SELECT SUM(CASE WHEN t.stop_reason = 'max_tokens' THEN 1 ELSE 0 END) FROM turns t WHERE t.session_id = s.session_id), 0) as truncations
        FROM sessions s
        WHERE s.first_timestamp IS NOT NULL {date_filter}
        ORDER BY cost DESC
        LIMIT 800
    """, params)
    rows = await cursor.fetchall()

    points: List[Dict[str, Any]] = []
    with_thinking = 0
    with_truncation = 0
    high_cost_low_output = 0
    total_cost = 0.0
    total_loc = 0

    for row in rows:
        cost = float(row[4] or 0)
        thinking = int(row[5] or 0)
        input_tokens = int(row[6] or 0)
        output_tokens = int(row[7] or 0)
        cache_read_tokens = int(row[8] or 0)
        loc_written = int(row[9] or 0)
        truncations = int(row[10] or 0)

        denom_input = float(input_tokens + cache_read_tokens)
        token_mix_ratio = (output_tokens / denom_input) if denom_input > 0 else 0.0
        output_per_cost = (output_tokens / cost) if cost > 0 else 0.0
        loc_per_cost = (loc_written / cost) if cost > 0 else 0.0
        efficiency_score = output_per_cost + (loc_per_cost * 0.5) - (thinking * 0.001)

        if thinking > 0:
            with_thinking += 1
        if truncations > 0:
            with_truncation += 1
        if cost >= 0.1 and (output_tokens < 800 or loc_written < 25):
            high_cost_low_output += 1

        total_cost += cost
        total_loc += loc_written

        points.append({
            "session_id": str(row[0]),
            "project": str(row[1]),
            "branch": str(row[2]),
            "model": str(row[3]),
            "cost": round(cost, 6),
            "thinking_chars": thinking,
            "input_tokens": input_tokens,
            "output_tokens": output_tokens,
            "cache_read_tokens": cache_read_tokens,
            "loc_written": loc_written,
            "truncations": truncations,
            "token_mix_ratio": round(float(token_mix_ratio), 6),
            "output_per_cost": round(float(output_per_cost), 6),
            "efficiency_score": round(float(efficiency_score), 6),
        })

    stop_params: list = []
    stop_filter = build_date_filter("t.timestamp", date_from, date_to, stop_params)
    cursor = await db.execute(f"""
        SELECT
            COALESCE(t.stop_reason, 'none') as stop_reason,
            COUNT(*) as cnt
        FROM turns t
        JOIN sessions s ON t.session_id = s.session_id
        WHERE t.timestamp IS NOT NULL {stop_filter}
        GROUP BY stop_reason
        ORDER BY cnt DESC
    """, stop_params)
    stop_rows = await cursor.fetchall()
    total_stop = sum(int(r[1] or 0) for r in stop_rows) or 1

    points_sorted = sorted(points, key=lambda p: (p["efficiency_score"], -p["cost"]))
    outliers = points_sorted[:30]

    return {
        "summary": {
            "total_sessions": len(points),
            "sessions_with_thinking": with_thinking,
            "sessions_with_truncation": with_truncation,
            "high_cost_low_output_sessions": high_cost_low_output,
            "avg_cost_per_loc": (total_cost / total_loc) if total_loc > 0 else 0.0,
        },
        "funnel": [
            {"stage": "sessions_total", "value": len(points)},
            {"stage": "sessions_with_thinking", "value": with_thinking},
            {"stage": "sessions_with_truncation", "value": with_truncation},
            {"stage": "high_cost_low_output", "value": high_cost_low_output},
        ],
        "by_stop_reason": [{
            "stop_reason": str(r[0]),
            "count": int(r[1] or 0),
            "percentage": (int(r[1] or 0) / total_stop),
        } for r in stop_rows],
        "scatter": points[:500],
        "outliers": outliers,
    }


async def get_workflow_bottlenecks_dashboard(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
) -> Dict[str, Any]:
    """Get transition matrix, retry loops, failure handoffs, and blocked sessions."""
    params: list = []
    date_filter = build_date_filter("tc.timestamp", date_from, date_to, params)
    cursor = await db.execute(f"""
        SELECT
            tc.session_id,
            COALESCE(s.project_display, s.project_path) as project,
            COALESCE(s.git_branch, 'unknown') as branch,
            CASE WHEN s.is_agent = 1 THEN 'agent' ELSE 'user' END as user_type,
            COALESCE(tc.tool_name, 'unknown') as tool_name,
            tc.success
        FROM tool_calls tc
        JOIN sessions s ON tc.session_id = s.session_id
        WHERE tc.timestamp IS NOT NULL {date_filter}
        ORDER BY tc.session_id, tc.timestamp, tc.id
    """, params)
    rows = await cursor.fetchall()

    transition_counter: Counter = Counter()
    transition_failures: Counter = Counter()
    session_failures: defaultdict = defaultdict(int)
    session_retries: defaultdict = defaultdict(int)
    session_meta: Dict[str, Dict[str, Any]] = {}
    retry_counter: Counter = Counter()

    prev_tool_by_session: Dict[str, str] = {}
    prev_success_by_session: Dict[str, int] = {}
    for sess_id, project, branch, user_type, tool_name, success in rows:
        session_meta[sess_id] = {"project": project, "branch": branch, "user_type": user_type}
        prev_tool = prev_tool_by_session.get(sess_id, "START")
        key = (prev_tool, tool_name)
        transition_counter[key] += 1

        succ = int(success or 0)
        if succ == 0:
            transition_failures[key] += 1
            session_failures[sess_id] += 1

        if prev_tool_by_session.get(sess_id) == tool_name and int(prev_success_by_session.get(sess_id, 1)) == 0:
            retry_counter[(sess_id, tool_name)] += 1
            session_retries[sess_id] += 1

        prev_tool_by_session[sess_id] = tool_name
        prev_success_by_session[sess_id] = succ

    transition_matrix = []
    for (from_tool, to_tool), count in transition_counter.most_common(150):
        failures = int(transition_failures.get((from_tool, to_tool), 0))
        transition_matrix.append({
            "from_tool": from_tool,
            "to_tool": to_tool,
            "count": int(count),
            "failures": failures,
            "failure_rate": (failures / count) if count > 0 else 0.0,
        })

    retry_loops = []
    for (sess_id, tool), retries in retry_counter.most_common(60):
        meta = session_meta.get(sess_id, {})
        retry_loops.append({
            "session_id": sess_id,
            "tool_name": tool,
            "retries": int(retries),
            "branch": meta.get("branch", "unknown"),
            "user_type": meta.get("user_type", "user"),
        })

    handoff_params: list = []
    handoff_date_filter = build_date_filter("c.first_timestamp", date_from, date_to, handoff_params)
    cursor = await db.execute(f"""
        SELECT
            p.session_id as parent_session_id,
            c.session_id as child_session_id,
            COALESCE(c.git_branch, 'unknown') as branch,
            CASE
                WHEN p.is_agent = 0 AND c.is_agent = 1 THEN 'human->agent'
                WHEN p.is_agent = 1 AND c.is_agent = 0 THEN 'agent->human'
                ELSE 'same_type'
            END as handoff,
            COALESCE((SELECT SUM(CASE WHEN tc.success = 0 THEN 1 ELSE 0 END)
                      FROM tool_calls tc WHERE tc.session_id = c.session_id), 0) as errors,
            COALESCE((SELECT COUNT(*) FROM tool_calls tc
                      WHERE tc.session_id = c.session_id), 0) as total_calls
        FROM sessions c
        JOIN sessions p ON c.parent_session_id = p.session_id
        WHERE c.parent_session_id IS NOT NULL {handoff_date_filter}
        ORDER BY errors DESC, total_calls DESC
        LIMIT 120
    """, handoff_params)
    handoff_rows = await cursor.fetchall()
    failure_handoffs = []
    for parent_sid, child_sid, branch, handoff, errors, total_calls in handoff_rows:
        e = int(errors or 0)
        t = int(total_calls or 0)
        if e <= 0:
            continue
        failure_handoffs.append({
            "parent_session_id": str(parent_sid),
            "child_session_id": str(child_sid),
            "branch": str(branch),
            "handoff": str(handoff),
            "errors": e,
            "error_rate": (e / t) if t > 0 else 0.0,
        })

    blocked_sessions = []
    all_sessions = set(list(session_failures.keys()) + list(session_retries.keys()))
    for sess_id in all_sessions:
        failures = int(session_failures.get(sess_id, 0))
        retries = int(session_retries.get(sess_id, 0))
        stall_score = failures * 2 + retries
        meta = session_meta.get(sess_id, {})
        blocked_sessions.append({
            "session_id": sess_id,
            "project": meta.get("project", "unknown"),
            "branch": meta.get("branch", "unknown"),
            "user_type": meta.get("user_type", "user"),
            "failures": failures,
            "retries": retries,
            "stall_score": stall_score,
        })
    blocked_sessions.sort(key=lambda x: x["stall_score"], reverse=True)

    return {
        "transition_matrix": transition_matrix[:120],
        "retry_loops": retry_loops[:50],
        "failure_handoffs": failure_handoffs[:50],
        "blocked_sessions": blocked_sessions[:50],
    }
