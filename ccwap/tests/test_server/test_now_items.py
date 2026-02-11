"""Focused regression tests for current NOW items."""

import pytest

from ccwap.server.queries import project_queries, workflow_queries


@pytest.mark.asyncio
class TestWorkflowOptimizations:
    """Tests for workflow/correctness fixes."""

    async def test_tool_sequences_do_not_cross_session_boundaries(self, async_db):
        """Sliding windows should be computed within each session only."""
        result = await workflow_queries.get_tool_sequences(async_db, window=3)

        sequences = {tuple(item["sequence"]) for item in result}
        assert ("Write", "Read", "Write") in sequences
        assert ("Read", "Write", "Bash") in sequences

        # These would only appear if windows crossed session boundaries.
        assert ("Write", "Bash", "Edit") not in sequences
        assert ("Bash", "Edit", "Bash") not in sequences

        total_windows = sum(item["count"] for item in result)
        assert total_windows == 2

    async def test_project_agent_spawns_counts_distinct_agent_sessions(self, async_db):
        """Agent spawn count should not increase with extra turns in the same session."""
        await async_db.execute(
            """
            INSERT INTO turns (session_id, uuid, entry_type, timestamp, model, cost)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("sess-003", "u11", "assistant", "2026-02-04T12:15:00", "claude-haiku-4-5-20251001", 0.02),
        )
        await async_db.commit()

        projects, _ = await project_queries.get_projects(
            async_db,
            date_from="2026-02-03",
            date_to="2026-02-05",
        )
        proj_beta = next(p for p in projects if p["project_path"] == "/path/proj-beta")
        assert proj_beta["agent_spawns"] == 1


@pytest.mark.asyncio
class TestExplorerDrilldownEndpoint:
    """Tests for in-page explorer drill-down API."""

    async def test_drilldown_group_only_returns_matching_sessions(self, client):
        resp = await client.get(
            "/api/explorer/drilldown"
            "?metric=cost&group_by=project&group_value=proj-alpha"
            "&from=2026-02-03&to=2026-02-05"
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["bucket"]["metric"] == "cost"
        assert data["bucket"]["group_by"] == "project"
        assert data["bucket"]["group_value"] == "proj-alpha"
        assert data["pagination"]["total_count"] == 2
        session_ids = {s["session_id"] for s in data["sessions"]}
        assert session_ids == {"sess-001", "sess-002"}

    async def test_drilldown_group_split_returns_expected_session(self, client):
        resp = await client.get(
            "/api/explorer/drilldown"
            "?metric=tool_calls_count&group_by=project&group_value=proj-alpha"
            "&split_by=language&split_value=python"
            "&from=2026-02-03&to=2026-02-05"
        )
        assert resp.status_code == 200

        data = resp.json()
        assert data["pagination"]["total_count"] == 1
        assert len(data["sessions"]) == 1
        assert data["sessions"][0]["session_id"] == "sess-001"
        assert data["sessions"][0]["bucket_value"] == 3.0

    async def test_drilldown_requires_split_value_when_split_by_provided(self, client):
        resp = await client.get(
            "/api/explorer/drilldown"
            "?metric=cost&group_by=project&group_value=proj-alpha&split_by=branch"
        )
        assert resp.status_code == 400
        assert "split_value is required" in resp.json()["detail"]

    async def test_drilldown_rejects_split_value_without_split_by(self, client):
        resp = await client.get(
            "/api/explorer/drilldown"
            "?metric=cost&group_by=project&group_value=proj-alpha&split_value=main"
        )
        assert resp.status_code == 400
        assert "split_value requires split_by" in resp.json()["detail"]
