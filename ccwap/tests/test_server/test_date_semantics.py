"""Regression tests for date semantics and localtime day buckets."""

import os
import time

import pytest

from ccwap.server.queries import model_queries, project_detail_queries, workflow_queries


def _set_test_timezone(tz_name: str):
    """Set process timezone for tests when supported."""
    if not hasattr(time, "tzset"):
        return None
    old_tz = os.environ.get("TZ")
    os.environ["TZ"] = tz_name
    time.tzset()
    return old_tz


def _restore_test_timezone(old_tz):
    """Restore process timezone after test."""
    if not hasattr(time, "tzset"):
        return
    if old_tz is None:
        os.environ.pop("TZ", None)
    else:
        os.environ["TZ"] = old_tz
    time.tzset()


@pytest.mark.asyncio
async def test_boundary_timestamp_uses_localtime_day_bucket(async_db):
    """
    Trend queries should bucket boundary timestamps by local day.

    This guards against cross-page mismatches where one page used UTC
    day bucketing and another used localtime.
    """
    old_tz = _set_test_timezone("Etc/GMT+8")
    try:
        boundary_ts = "2026-01-15T00:30:00"
        raw_utc_date = "2026-01-15"

        cursor = await async_db.execute(
            "SELECT date(?, 'localtime')",
            (boundary_ts,),
        )
        local_bucket = (await cursor.fetchone())[0]
        assert local_bucket is not None

        # If timezone override is available but no offset was applied,
        # skip strict boundary assertions instead of producing a false failure.
        if hasattr(time, "tzset") and local_bucket == raw_utc_date:
            pytest.skip("timezone override did not shift local day bucket on this platform")

        await async_db.execute("""
            INSERT INTO sessions (
                session_id, project_path, project_display, first_timestamp, last_timestamp,
                duration_seconds, is_agent, cc_version, git_branch, file_path
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            "sess-boundary-001",
            "/path/proj-boundary",
            "proj-boundary",
            boundary_ts,
            boundary_ts,
            60,
            1,
            "1.0.99",
            "boundary",
            "/logs/s-boundary.jsonl",
        ))

        await async_db.execute("""
            INSERT INTO turns (
                session_id, uuid, entry_type, timestamp, model, cost
            ) VALUES (?, ?, ?, ?, ?, ?)
        """, (
            "sess-boundary-001",
            "u-boundary-001",
            "assistant",
            boundary_ts,
            "claude-boundary-model",
            0.123,
        ))
        await async_db.commit()

        model_trend = await model_queries.get_model_usage_trend(
            async_db,
            date_from=local_bucket,
            date_to=local_bucket,
        )
        boundary_model = next((r for r in model_trend if r["model"] == "claude-boundary-model"), None)
        assert boundary_model is not None
        assert boundary_model["date"] == local_bucket

        workflow_trend = await workflow_queries.get_user_type_trend(
            async_db,
            date_from=local_bucket,
            date_to=local_bucket,
        )
        agent_bucket = next((r for r in workflow_trend if r["user_type"] == "agent"), None)
        assert agent_bucket is not None
        assert agent_bucket["date"] == local_bucket

        detail = await project_detail_queries.get_project_detail(
            async_db,
            "/path/proj-boundary",
            date_from=local_bucket,
            date_to=local_bucket,
        )
        assert detail is not None
        assert [p["date"] for p in detail["cost_trend"]] == [local_bucket]
    finally:
        _restore_test_timezone(old_tz)

