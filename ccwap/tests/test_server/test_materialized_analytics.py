"""Tests for optional materialized analytics aggregates."""

import pytest

from ccwap.server.queries.explorer_queries import query_explorer
from ccwap.server.queries.materialized_queries import refresh_materialized_analytics


def _normalize_rows(rows):
    return sorted(
        (r["group"], r.get("split"), round(float(r["value"]), 6))
        for r in rows
    )


@pytest.mark.asyncio
async def test_query_explorer_materialized_falls_back_when_not_backfilled(async_db):
    """`use_materialized=True` should fall back to raw when aggregate tables are empty."""
    raw_rows, raw_meta = await query_explorer(
        async_db,
        metric="cost",
        group_by="project",
        split_by="is_agent",
        date_from="2026-02-03",
        date_to="2026-02-05",
        use_materialized=False,
    )
    mat_rows, mat_meta = await query_explorer(
        async_db,
        metric="cost",
        group_by="project",
        split_by="is_agent",
        date_from="2026-02-03",
        date_to="2026-02-05",
        use_materialized=True,
    )

    assert _normalize_rows(mat_rows) == _normalize_rows(raw_rows)
    assert mat_meta["total"] == raw_meta["total"]
    assert mat_meta["row_count"] == raw_meta["row_count"]


@pytest.mark.asyncio
async def test_refresh_materialized_analytics_populates_tables(async_db):
    stats = await refresh_materialized_analytics(async_db)
    assert stats["turns_agg_daily"] > 0
    assert stats["tool_calls_agg_daily"] > 0
    assert stats["sessions_agg_daily"] > 0


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "metric,group_by,split_by",
    [
        ("cost", "project", "is_agent"),
        ("tool_calls_count", "project", "language"),
        ("sessions_count", "date", "is_agent"),
    ],
)
async def test_query_explorer_materialized_matches_raw(async_db, metric, group_by, split_by):
    await refresh_materialized_analytics(async_db)

    raw_rows, raw_meta = await query_explorer(
        async_db,
        metric=metric,
        group_by=group_by,
        split_by=split_by,
        date_from="2026-02-03",
        date_to="2026-02-05",
        use_materialized=False,
    )
    mat_rows, mat_meta = await query_explorer(
        async_db,
        metric=metric,
        group_by=group_by,
        split_by=split_by,
        date_from="2026-02-03",
        date_to="2026-02-05",
        use_materialized=True,
    )

    assert _normalize_rows(mat_rows) == _normalize_rows(raw_rows)
    assert round(float(mat_meta["total"]), 6) == round(float(raw_meta["total"]), 6)
    assert mat_meta["row_count"] == raw_meta["row_count"]
    assert mat_meta["groups"] == raw_meta["groups"]
    assert mat_meta["splits"] == raw_meta["splits"]

