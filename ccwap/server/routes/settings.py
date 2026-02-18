"""Settings API endpoint."""

import csv
import io
import json
import zipfile
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import StreamingResponse

import aiosqlite

from ccwap.server.dependencies import get_db, get_config
from ccwap.server.models.settings import (
    SettingsResponse,
    PricingEntry,
    PricingUpdateRequest,
    DatabaseStats,
    EtlStatus,
)
from ccwap.server.queries.settings_queries import get_db_stats, get_etl_status

router = APIRouter(prefix="/api", tags=["settings"])

EXPORT_TABLES = [
    "sessions", "turns", "tool_calls", "experiment_tags",
    "daily_summaries", "etl_state", "snapshots",
    "saved_views", "alert_rules",
]


@router.get("/settings", response_model=SettingsResponse)
async def get_settings(
    request: Request,
    db: aiosqlite.Connection = Depends(get_db),
):
    """Get current settings including pricing, ETL status, and DB stats."""
    config = get_config(request)

    # Build pricing response
    pricing_table = config.get("pricing", {})
    pricing = {}
    for model, prices in pricing_table.items():
        if model == "default":
            continue
        cache_write_5m = prices.get("cache_write_5m", prices.get("cache_write", 0))
        cache_write_1h = prices.get("cache_write_1h", cache_write_5m * 1.6)
        pricing[model] = PricingEntry(
            input=prices.get("input", 0),
            output=prices.get("output", 0),
            cache_read=prices.get("cache_read", 0),
            cache_write_5m=cache_write_5m,
            cache_write_1h=cache_write_1h,
            cache_write=cache_write_5m,
        )

    db_stats_raw = await get_db_stats(db)
    etl_status_raw = await get_etl_status(db)

    return SettingsResponse(
        pricing=pricing,
        etl_status=EtlStatus(**etl_status_raw),
        db_stats=DatabaseStats(**db_stats_raw),
        version=config.get("pricing_version", ""),
    )


@router.put("/settings/pricing")
async def update_pricing(
    request_body: PricingUpdateRequest,
    request: Request,
):
    """Update pricing for a model."""
    config = get_config(request)
    pricing = config.get("pricing", {})
    cache_write_5m = request_body.pricing.cache_write_5m
    cache_write_1h = request_body.pricing.cache_write_1h
    pricing[request_body.model] = {
        "input": request_body.pricing.input,
        "output": request_body.pricing.output,
        "cache_read": request_body.pricing.cache_read,
        "cache_write_5m": cache_write_5m,
        "cache_write_1h": cache_write_1h,
        # Preserve legacy key for compatibility with older tooling.
        "cache_write": cache_write_5m,
    }

    from ccwap.config.loader import save_config
    save_config(config)

    return {"status": "ok", "model": request_body.model}


@router.post("/settings/rebuild")
async def trigger_rebuild(request: Request):
    """Trigger a full ETL rebuild."""
    config = get_config(request)

    from ccwap.etl import run_etl
    stats = run_etl(force_rebuild=True, config=config)

    return {"status": "ok", "stats": stats}


@router.get("/settings/export")
async def export_database(
    request: Request,
    format: str = Query(default="csv", pattern="^(csv|json)$"),
    db: aiosqlite.Connection = Depends(get_db),
):
    """
    Export all database tables as a ZIP file containing CSV or JSON files.

    Args:
        format: Export format - 'csv' (default) or 'json'
    """
    buf = io.BytesIO()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for table in EXPORT_TABLES:
            cursor = await db.execute(f"SELECT * FROM {table}")  # noqa: S608
            columns = [desc[0] for desc in cursor.description]
            rows = await cursor.fetchall()

            if format == "json":
                data = [dict(zip(columns, row)) for row in rows]
                content = json.dumps(data, indent=2, default=str)
                zf.writestr(f"{table}.json", content)
            else:
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(columns)
                for row in rows:
                    writer.writerow(row)
                zf.writestr(f"{table}.csv", output.getvalue())

    buf.seek(0)
    filename = f"ccwap_export_{timestamp}.zip"

    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )
