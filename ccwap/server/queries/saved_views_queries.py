"""Queries for persisted saved views and alert rules."""

import json
from typing import Any, Dict, List, Optional

import aiosqlite

from ccwap.server.queries.cost_queries import get_cost_summary
from ccwap.server.queries.explorer_queries import query_explorer
from ccwap.server.queries.productivity_queries import get_efficiency_summary


VALID_OPERATORS = {">", ">=", "<", "<=", "==", "!="}


def _encode_filters(filters: Dict[str, Any]) -> str:
    return json.dumps(filters or {}, separators=(",", ":"))


def _decode_filters(raw: Optional[str]) -> Dict[str, Any]:
    if not raw:
        return {}
    try:
        decoded = json.loads(raw)
        return decoded if isinstance(decoded, dict) else {}
    except Exception:
        return {}


def _compare_value(current: float, operator: str, threshold: float) -> bool:
    if operator == ">":
        return current > threshold
    if operator == ">=":
        return current >= threshold
    if operator == "<":
        return current < threshold
    if operator == "<=":
        return current <= threshold
    if operator == "==":
        return current == threshold
    if operator == "!=":
        return current != threshold
    return False


def _as_list(value: Any) -> Optional[List[str]]:
    """Normalize saved filter values to list[str] for explorer query inputs."""
    if value is None:
        return None
    if isinstance(value, list):
        items = [str(v).strip() for v in value if str(v).strip()]
        return items or None
    if isinstance(value, str):
        items = [v.strip() for v in value.split(",") if v.strip()]
        return items or None
    return None


async def list_saved_views(
    db: aiosqlite.Connection,
    page: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params: list = []
    where = ""
    if page:
        where = "WHERE page = ?"
        params.append(page)

    cursor = await db.execute(f"""
        SELECT id, name, page, filters_json, created_at
        FROM saved_views
        {where}
        ORDER BY created_at DESC, id DESC
    """, params)
    rows = await cursor.fetchall()
    return [{
        "id": int(r[0]),
        "name": str(r[1]),
        "page": str(r[2]),
        "filters": _decode_filters(r[3]),
        "created_at": r[4],
    } for r in rows]


async def create_saved_view(
    db: aiosqlite.Connection,
    name: str,
    page: str,
    filters: Dict[str, Any],
) -> Dict[str, Any]:
    cursor = await db.execute("""
        INSERT INTO saved_views (name, page, filters_json)
        VALUES (?, ?, ?)
    """, (name, page, _encode_filters(filters)))
    await db.commit()
    view_id = int(cursor.lastrowid)
    cursor = await db.execute("""
        SELECT id, name, page, filters_json, created_at
        FROM saved_views
        WHERE id = ?
    """, (view_id,))
    row = await cursor.fetchone()
    return {
        "id": int(row[0]),
        "name": str(row[1]),
        "page": str(row[2]),
        "filters": _decode_filters(row[3]),
        "created_at": row[4],
    }


async def delete_saved_view(db: aiosqlite.Connection, view_id: int) -> int:
    cursor = await db.execute("DELETE FROM saved_views WHERE id = ?", (view_id,))
    await db.commit()
    return int(cursor.rowcount or 0)


async def list_alert_rules(
    db: aiosqlite.Connection,
    page: Optional[str] = None,
) -> List[Dict[str, Any]]:
    params: list = []
    where = ""
    if page:
        where = "WHERE page = ?"
        params.append(page)
    cursor = await db.execute(f"""
        SELECT id, name, page, metric, operator, threshold, filters_json, enabled, created_at
        FROM alert_rules
        {where}
        ORDER BY created_at DESC, id DESC
    """, params)
    rows = await cursor.fetchall()
    return [{
        "id": int(r[0]),
        "name": str(r[1]),
        "page": str(r[2]),
        "metric": str(r[3]),
        "operator": str(r[4]),
        "threshold": float(r[5] or 0),
        "filters": _decode_filters(r[6]),
        "enabled": bool(r[7]),
        "created_at": r[8],
    } for r in rows]


async def create_alert_rule(
    db: aiosqlite.Connection,
    name: str,
    page: str,
    metric: str,
    operator: str,
    threshold: float,
    filters: Dict[str, Any],
    enabled: bool = True,
) -> Dict[str, Any]:
    if operator not in VALID_OPERATORS:
        raise ValueError(f"Invalid operator '{operator}'")
    cursor = await db.execute("""
        INSERT INTO alert_rules (name, page, metric, operator, threshold, filters_json, enabled)
        VALUES (?, ?, ?, ?, ?, ?, ?)
    """, (name, page, metric, operator, threshold, _encode_filters(filters), 1 if enabled else 0))
    await db.commit()
    alert_id = int(cursor.lastrowid)
    cursor = await db.execute("""
        SELECT id, name, page, metric, operator, threshold, filters_json, enabled, created_at
        FROM alert_rules
        WHERE id = ?
    """, (alert_id,))
    row = await cursor.fetchone()
    return {
        "id": int(row[0]),
        "name": str(row[1]),
        "page": str(row[2]),
        "metric": str(row[3]),
        "operator": str(row[4]),
        "threshold": float(row[5] or 0),
        "filters": _decode_filters(row[6]),
        "enabled": bool(row[7]),
        "created_at": row[8],
    }


async def delete_alert_rule(db: aiosqlite.Connection, rule_id: int) -> int:
    cursor = await db.execute("DELETE FROM alert_rules WHERE id = ?", (rule_id,))
    await db.commit()
    return int(cursor.rowcount or 0)


async def evaluate_alert_rules(
    db: aiosqlite.Connection,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    page: Optional[str] = None,
) -> List[Dict[str, Any]]:
    rules = await list_alert_rules(db, page=page)
    enabled_rules = [r for r in rules if r["enabled"]]
    evaluations: List[Dict[str, Any]] = []

    for rule in enabled_rules:
        filters = rule["filters"]
        metric = rule["metric"]
        current_value = 0.0

        if rule["page"] == "cost":
            summary = await get_cost_summary(db, date_from=date_from, date_to=date_to)
            if metric == "total_cost":
                current_value = float(summary.get("total_cost", 0.0))
            elif metric == "avg_daily_cost":
                current_value = float(summary.get("avg_daily_cost", 0.0))

        elif rule["page"] == "productivity":
            summary = await get_efficiency_summary(db, date_from=date_from, date_to=date_to)
            if metric == "error_rate":
                current_value = float(summary.get("error_rate", 0.0))
            elif metric == "loc_written":
                current_value = float(summary.get("total_loc_written", 0.0))
            elif metric == "cost_per_kloc":
                current_value = float(summary.get("cost_per_kloc", 0.0))

        elif rule["page"] == "explorer":
            rows, meta = await query_explorer(
                db,
                metric=str(filters.get("metric", "cost")),
                group_by=str(filters.get("group_by", "project")),
                split_by=filters.get("split_by"),
                date_from=date_from,
                date_to=date_to,
                projects=_as_list(filters.get("projects")),
                models=_as_list(filters.get("models")),
                branches=_as_list(filters.get("branches")),
                languages=_as_list(filters.get("languages")),
            )
            _ = rows
            current_value = float(meta.get("total", 0.0))

        triggered = _compare_value(float(current_value), rule["operator"], float(rule["threshold"]))
        evaluations.append({
            "rule_id": rule["id"],
            "name": rule["name"],
            "page": rule["page"],
            "metric": rule["metric"],
            "operator": rule["operator"],
            "threshold": float(rule["threshold"]),
            "current_value": float(current_value),
            "triggered": bool(triggered),
        })

    return evaluations
