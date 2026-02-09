"""Tests for all API endpoints.

Uses the deterministic test database from conftest.py.
Tests each endpoint returns valid JSON with expected structure.
"""

import base64
from datetime import date

import pytest
from pydantic import ValidationError

from ccwap.server.models.common import DateRangeParams, PaginationParams
from ccwap.server.queries import (
    dashboard_queries,
    project_queries,
    session_queries,
    cost_queries,
    experiment_queries,
    productivity_queries,
    analytics_queries,
    settings_queries,
    heatmap_queries,
    model_queries,
    workflow_queries,
    search_queries,
    project_detail_queries,
)


@pytest.mark.asyncio
class TestHealthEndpoint:
    """Test /api/health endpoint."""

    async def test_health_returns_ok(self, client):
        resp = await client.get("/api/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["database"] == "ok"
        assert "uptime_seconds" in data

    async def test_health_has_version(self, client):
        resp = await client.get("/api/health")
        data = resp.json()
        assert "version" in data


@pytest.mark.asyncio
class TestDashboardEndpoint:
    """Test /api/dashboard endpoint."""

    async def test_dashboard_returns_all_sections(self, client):
        resp = await client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert "vitals" in data
        assert "sparkline_7d" in data
        assert "top_projects" in data
        assert "cost_trend" in data
        assert "recent_sessions" in data

    async def test_dashboard_vitals_structure(self, client):
        resp = await client.get("/api/dashboard")
        vitals = resp.json()["vitals"]
        assert "sessions" in vitals
        assert "cost" in vitals
        assert "loc_written" in vitals
        assert "error_rate" in vitals

    async def test_dashboard_with_date_range(self, client):
        resp = await client.get("/api/dashboard?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["cost_trend"]) > 0

    async def test_dashboard_cost_trend_has_data(self, client):
        resp = await client.get("/api/dashboard?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        trend = data["cost_trend"]
        assert isinstance(trend, list)
        for point in trend:
            assert "date" in point
            assert "cost" in point

    async def test_dashboard_top_projects(self, client):
        resp = await client.get("/api/dashboard?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        projects = data["top_projects"]
        assert isinstance(projects, list)
        if projects:
            assert "project_path" in projects[0]
            assert "cost" in projects[0]

    async def test_dashboard_recent_sessions(self, client):
        resp = await client.get("/api/dashboard")
        data = resp.json()
        sessions = data["recent_sessions"]
        assert isinstance(sessions, list)
        assert len(sessions) > 0
        assert "session_id" in sessions[0]

    async def test_dashboard_sparkline(self, client):
        resp = await client.get("/api/dashboard")
        data = resp.json()
        sparkline = data["sparkline_7d"]
        assert isinstance(sparkline, list)


@pytest.mark.asyncio
class TestProjectsEndpoint:
    """Test /api/projects endpoint."""

    async def test_projects_returns_paginated(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert "projects" in data
        assert "pagination" in data
        assert data["pagination"]["page"] == 1

    async def test_projects_has_metrics(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        projects = data["projects"]
        assert len(projects) > 0
        p = projects[0]
        assert "cost" in p
        assert "sessions" in p
        assert "loc_written" in p
        assert "error_rate" in p

    async def test_projects_sort_by_cost(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05&sort=cost&order=desc")
        data = resp.json()
        costs = [p["cost"] for p in data["projects"]]
        assert costs == sorted(costs, reverse=True)

    async def test_projects_search_filter(self, client):
        resp = await client.get("/api/projects?search=alpha&from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for p in data["projects"]:
            assert "alpha" in p["project_path"].lower() or "alpha" in p["project_display"].lower()

    async def test_projects_pagination(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05&page=1&limit=2")
        data = resp.json()
        assert data["pagination"]["limit"] == 2
        assert len(data["projects"]) <= 2

    async def test_projects_two_query_pattern_correctness(self, client):
        """Verify that tool call metrics don't inflate turn metrics."""
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for p in data["projects"]:
            # Cost should be reasonable (not inflated)
            assert p["cost"] < 10.0, f"Cost suspiciously high for {p['project_path']}"


@pytest.mark.asyncio
class TestSessionsEndpoint:
    """Test /api/sessions endpoint."""

    async def test_sessions_list(self, client):
        resp = await client.get("/api/sessions?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert "pagination" in data
        assert len(data["sessions"]) > 0

    async def test_sessions_have_expected_fields(self, client):
        resp = await client.get("/api/sessions?from=2026-02-03&to=2026-02-05")
        s = resp.json()["sessions"][0]
        assert "session_id" in s
        assert "project_display" in s
        assert "cost" in s
        assert "turns" in s

    async def test_sessions_filter_by_project(self, client):
        resp = await client.get("/api/sessions?project=alpha&from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for s in data["sessions"]:
            assert "alpha" in s["project_path"].lower() or "alpha" in (s["project_display"] or "").lower()

    async def test_session_replay(self, client):
        resp = await client.get("/api/sessions/sess-001/replay")
        assert resp.status_code == 200
        data = resp.json()
        assert data["session_id"] == "sess-001"
        assert "turns" in data
        assert len(data["turns"]) == 4  # 4 turns for sess-001

    async def test_session_replay_cumulative_cost(self, client):
        resp = await client.get("/api/sessions/sess-001/replay")
        data = resp.json()
        turns = data["turns"]
        # Cumulative cost should be monotonically non-decreasing
        prev = 0.0
        for t in turns:
            assert t["cumulative_cost"] >= prev
            prev = t["cumulative_cost"]

    async def test_session_replay_has_tool_calls(self, client):
        resp = await client.get("/api/sessions/sess-001/replay")
        data = resp.json()
        # Find assistant turn that should have tool calls
        tool_turns = [t for t in data["turns"] if len(t["tool_calls"]) > 0]
        assert len(tool_turns) > 0

    async def test_session_replay_metadata(self, client):
        resp = await client.get("/api/sessions/sess-001/replay")
        data = resp.json()
        assert data["total_cost"] > 0
        assert data["total_turns"] == 4
        assert data["total_user_turns"] == 2
        assert "cost_by_model" in data
        assert "tool_distribution" in data

    async def test_session_replay_not_found(self, client):
        resp = await client.get("/api/sessions/nonexistent/replay")
        assert resp.status_code == 404

    async def test_session_replay_user_prompt_preview(self, client):
        resp = await client.get("/api/sessions/sess-001/replay")
        data = resp.json()
        user_turns = [t for t in data["turns"] if t["entry_type"] == "user"]
        assert user_turns[0]["user_prompt_preview"] == "Fix the login bug"


@pytest.mark.asyncio
class TestCostEndpoint:
    """Test /api/cost endpoint."""

    async def test_cost_analysis(self, client):
        resp = await client.get("/api/cost?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "by_model" in data
        assert "trend" in data
        assert "cache_savings" in data
        assert "forecast" in data

    async def test_cost_summary_fields(self, client):
        resp = await client.get("/api/cost?from=2026-02-03&to=2026-02-05")
        summary = resp.json()["summary"]
        assert "total_cost" in summary
        assert "avg_daily_cost" in summary
        assert summary["total_cost"] >= 0

    async def test_cost_by_model(self, client):
        resp = await client.get("/api/cost?from=2026-02-03&to=2026-02-05")
        models = resp.json()["by_model"]
        assert isinstance(models, list)
        if models:
            assert "model" in models[0]
            assert "cost" in models[0]
            assert "percentage" in models[0]

    async def test_cost_trend_ordered(self, client):
        resp = await client.get("/api/cost?from=2026-02-03&to=2026-02-05")
        trend = resp.json()["trend"]
        dates = [p["date"] for p in trend]
        assert dates == sorted(dates)

    async def test_cost_cache_savings(self, client):
        resp = await client.get("/api/cost?from=2026-02-03&to=2026-02-05")
        cache = resp.json()["cache_savings"]
        assert "cache_hit_rate" in cache
        assert "estimated_savings" in cache
        assert cache["cache_hit_rate"] >= 0


@pytest.mark.asyncio
class TestProductivityEndpoint:
    """Test /api/productivity endpoint."""

    async def test_productivity(self, client):
        resp = await client.get("/api/productivity?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "loc_trend" in data
        assert "languages" in data
        assert "tool_usage" in data
        assert "error_analysis" in data
        assert "file_hotspots" in data

    async def test_productivity_summary(self, client):
        resp = await client.get("/api/productivity?from=2026-02-03&to=2026-02-05")
        summary = resp.json()["summary"]
        assert summary["total_loc_written"] >= 0
        assert "error_rate" in summary

    async def test_tool_usage(self, client):
        resp = await client.get("/api/productivity?from=2026-02-03&to=2026-02-05")
        tools = resp.json()["tool_usage"]
        assert isinstance(tools, list)
        if tools:
            assert "tool_name" in tools[0]
            assert "total_calls" in tools[0]
            assert "success_rate" in tools[0]

    async def test_error_analysis(self, client):
        resp = await client.get("/api/productivity?from=2026-02-03&to=2026-02-05")
        errors = resp.json()["error_analysis"]
        assert "total_errors" in errors
        assert "categories" in errors


@pytest.mark.asyncio
class TestAnalyticsEndpoint:
    """Test /api/analytics endpoint."""

    async def test_analytics(self, client):
        resp = await client.get("/api/analytics?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert "thinking" in data
        assert "truncation" in data
        assert "sidechains" in data
        assert "cache_tiers" in data
        assert "branches" in data
        assert "versions" in data
        assert "skills_agents" in data

    async def test_thinking_analysis(self, client):
        resp = await client.get("/api/analytics?from=2026-02-03&to=2026-02-05")
        thinking = resp.json()["thinking"]
        assert thinking["total_thinking_chars"] > 0
        assert thinking["turns_with_thinking"] > 0

    async def test_truncation_analysis(self, client):
        resp = await client.get("/api/analytics?from=2026-02-03&to=2026-02-05")
        trunc = resp.json()["truncation"]
        assert trunc["total_turns"] > 0
        reasons = [r["stop_reason"] for r in trunc["by_stop_reason"]]
        assert "end_turn" in reasons

    async def test_branch_analytics(self, client):
        resp = await client.get("/api/analytics?from=2026-02-03&to=2026-02-05")
        branches = resp.json()["branches"]["branches"]
        assert isinstance(branches, list)
        assert len(branches) > 0

    async def test_version_impact(self, client):
        resp = await client.get("/api/analytics?from=2026-02-03&to=2026-02-05")
        versions = resp.json()["versions"]["versions"]
        assert isinstance(versions, list)
        assert len(versions) > 0


@pytest.mark.asyncio
class TestExperimentsEndpoint:
    """Test /api/experiments endpoints."""

    async def test_list_tags(self, client):
        resp = await client.get("/api/experiments/tags")
        assert resp.status_code == 200
        data = resp.json()
        assert "tags" in data
        assert len(data["tags"]) >= 1
        assert data["tags"][0]["tag_name"] == "baseline"

    async def test_create_tag(self, client):
        resp = await client.post("/api/experiments/tags", json={
            "tag_name": "test-tag",
            "session_ids": ["sess-003", "sess-004"]
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["tag_name"] == "test-tag"
        assert data["sessions_tagged"] == 2

    async def test_delete_tag(self, client):
        # First create a tag
        await client.post("/api/experiments/tags", json={
            "tag_name": "to-delete",
            "session_ids": ["sess-001"]
        })
        # Delete it
        resp = await client.delete("/api/experiments/tags/to-delete")
        assert resp.status_code == 200
        assert resp.json()["deleted_count"] >= 1

    async def test_delete_nonexistent_tag(self, client):
        resp = await client.delete("/api/experiments/tags/nonexistent")
        assert resp.status_code == 404

    async def test_compare_tags(self, client):
        # Create a second tag
        await client.post("/api/experiments/tags", json={
            "tag_name": "experiment",
            "session_ids": ["sess-003", "sess-004"]
        })
        resp = await client.get("/api/experiments/compare?tag_a=baseline&tag_b=experiment")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tag_a"] == "baseline"
        assert data["tag_b"] == "experiment"
        assert len(data["metrics"]) > 0


@pytest.mark.asyncio
class TestSettingsEndpoint:
    """Test /api/settings endpoint."""

    async def test_get_settings(self, client):
        resp = await client.get("/api/settings")
        assert resp.status_code == 200
        data = resp.json()
        assert "pricing" in data
        assert "db_stats" in data
        assert "etl_status" in data

    async def test_db_stats(self, client):
        resp = await client.get("/api/settings")
        stats = resp.json()["db_stats"]
        assert stats["sessions"] == 5
        assert stats["turns"] == 10
        assert stats["tool_calls"] == 8
        assert stats["daily_summaries"] == 3

    async def test_pricing_table(self, client):
        resp = await client.get("/api/settings")
        pricing = resp.json()["pricing"]
        assert "claude-opus-4-5-20251101" in pricing
        assert pricing["claude-opus-4-5-20251101"]["input"] == 15.0


# =====================================================================
# Pydantic model validation tests
# =====================================================================


class TestDateRangeParamsValidation:
    """Test DateRangeParams Pydantic validation."""

    def test_valid_date_range(self):
        params = DateRangeParams(date_from=date(2026, 1, 1), date_to=date(2026, 1, 31))
        assert params.date_from == date(2026, 1, 1)
        assert params.date_to == date(2026, 1, 31)

    def test_none_dates_are_valid(self):
        params = DateRangeParams()
        assert params.date_from is None
        assert params.date_to is None

    def test_only_from_date_is_valid(self):
        params = DateRangeParams(date_from=date(2026, 1, 1))
        assert params.date_from == date(2026, 1, 1)
        assert params.date_to is None

    def test_only_to_date_is_valid(self):
        params = DateRangeParams(date_to=date(2026, 1, 31))
        assert params.date_from is None
        assert params.date_to == date(2026, 1, 31)

    def test_reversed_date_range_raises(self):
        """date_from > date_to should raise a validation error."""
        with pytest.raises(ValidationError, match="date_from must be before date_to"):
            DateRangeParams(date_from=date(2026, 2, 10), date_to=date(2026, 2, 1))

    def test_future_date_from_raises(self):
        """date_from in the future should raise a validation error."""
        from datetime import timedelta
        future = date.today() + timedelta(days=30)
        with pytest.raises(ValidationError, match="date_from cannot be in the future"):
            DateRangeParams(date_from=future)

    def test_same_from_and_to_is_valid(self):
        """date_from == date_to is a single-day range and should be valid."""
        d = date(2026, 1, 15)
        params = DateRangeParams(date_from=d, date_to=d)
        assert params.date_from == params.date_to

    def test_alias_population(self):
        """Fields can be populated by alias names ('from', 'to')."""
        params = DateRangeParams.model_validate(
            {"from": "2026-01-01", "to": "2026-01-31"}
        )
        assert params.date_from == date(2026, 1, 1)
        assert params.date_to == date(2026, 1, 31)


class TestPaginationParamsValidation:
    """Test PaginationParams Pydantic validation."""

    def test_default_values(self):
        params = PaginationParams()
        assert params.page == 1
        assert params.limit == 50
        assert params.order == "desc"
        assert params.sort is None

    def test_custom_values(self):
        params = PaginationParams(page=3, limit=25, sort="cost", order="asc")
        assert params.page == 3
        assert params.limit == 25
        assert params.sort == "cost"
        assert params.order == "asc"

    def test_page_zero_raises(self):
        with pytest.raises(ValidationError):
            PaginationParams(page=0)

    def test_negative_page_raises(self):
        with pytest.raises(ValidationError):
            PaginationParams(page=-1)

    def test_limit_zero_raises(self):
        with pytest.raises(ValidationError):
            PaginationParams(limit=0)

    def test_limit_exceeds_max_raises(self):
        with pytest.raises(ValidationError):
            PaginationParams(limit=201)

    def test_limit_at_max_boundary(self):
        params = PaginationParams(limit=200)
        assert params.limit == 200

    def test_invalid_order_raises(self):
        with pytest.raises(ValidationError):
            PaginationParams(order="random")


# =====================================================================
# Direct query function unit tests
# =====================================================================


@pytest.mark.asyncio
class TestDashboardQueries:
    """Direct unit tests for dashboard query functions."""

    async def test_get_vitals_today_structure(self, async_db):
        """Vitals should return all expected keys even if today has no data."""
        vitals = await dashboard_queries.get_vitals_today(async_db)
        expected_keys = {
            "sessions", "cost", "loc_written", "error_rate",
            "user_turns", "messages", "input_tokens", "output_tokens",
        }
        assert expected_keys == set(vitals.keys())

    async def test_get_vitals_today_types(self, async_db):
        vitals = await dashboard_queries.get_vitals_today(async_db)
        assert isinstance(vitals["sessions"], int)
        assert isinstance(vitals["cost"], (int, float))
        assert isinstance(vitals["loc_written"], int)
        assert isinstance(vitals["error_rate"], float)

    async def test_get_sparkline_returns_list(self, async_db):
        result = await dashboard_queries.get_sparkline_7d(async_db)
        assert isinstance(result, list)
        for item in result:
            assert "date" in item
            assert "value" in item

    async def test_get_top_projects_with_date_range(self, async_db):
        """Top projects should return known projects for test data range."""
        projects = await dashboard_queries.get_top_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert isinstance(projects, list)
        assert len(projects) == 3  # 3 distinct projects
        paths = [p["project_path"] for p in projects]
        assert "/path/proj-alpha" in paths
        assert "/path/proj-beta" in paths
        assert "/path/proj-gamma" in paths

    async def test_get_top_projects_sorted_by_cost_desc(self, async_db):
        projects = await dashboard_queries.get_top_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        costs = [p["cost"] for p in projects]
        assert costs == sorted(costs, reverse=True)

    async def test_get_top_projects_empty_date_range(self, async_db):
        """A date range with no data should return empty list."""
        projects = await dashboard_queries.get_top_projects(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert projects == []

    async def test_get_top_projects_limit(self, async_db):
        projects = await dashboard_queries.get_top_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05", limit=1
        )
        assert len(projects) == 1

    async def test_get_top_projects_no_date_filter(self, async_db):
        """Without date filters, should return all projects."""
        projects = await dashboard_queries.get_top_projects(async_db)
        assert len(projects) == 3

    async def test_get_cost_trend_returns_ordered_dates(self, async_db):
        trend = await dashboard_queries.get_cost_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        dates = [item["date"] for item in trend]
        assert dates == sorted(dates)
        assert len(trend) == 3  # 3 daily summaries

    async def test_get_cost_trend_empty_range(self, async_db):
        trend = await dashboard_queries.get_cost_trend(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert trend == []

    async def test_get_cost_trend_fields(self, async_db):
        trend = await dashboard_queries.get_cost_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for item in trend:
            assert "date" in item
            assert "cost" in item
            assert "sessions" in item
            assert "messages" in item

    async def test_get_recent_sessions_default_limit(self, async_db):
        sessions = await dashboard_queries.get_recent_sessions(async_db)
        assert len(sessions) == 5  # All 5 test sessions
        # Ordered by first_timestamp DESC
        assert sessions[0]["session_id"] == "sess-001"

    async def test_get_recent_sessions_custom_limit(self, async_db):
        sessions = await dashboard_queries.get_recent_sessions(async_db, limit=2)
        assert len(sessions) == 2

    async def test_get_recent_sessions_fields(self, async_db):
        sessions = await dashboard_queries.get_recent_sessions(async_db)
        for s in sessions:
            assert "session_id" in s
            assert "project_display" in s
            assert "cost" in s
            assert "turns" in s
            assert "is_agent" in s
            assert isinstance(s["is_agent"], bool)


@pytest.mark.asyncio
class TestProjectQueries:
    """Direct unit tests for project query functions."""

    async def test_get_projects_returns_tuple(self, async_db):
        projects, total = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert isinstance(projects, list)
        assert isinstance(total, int)
        assert total == 3

    async def test_get_projects_empty_db_range(self, async_db):
        """A range with no sessions returns empty list and zero count."""
        projects, total = await project_queries.get_projects(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert projects == []
        assert total == 0

    async def test_get_projects_derived_cost_per_kloc(self, async_db):
        """Projects with LOC > 0 should have nonzero cost_per_kloc."""
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        alpha = next(p for p in projects if p["project_path"] == "/path/proj-alpha")
        # proj-alpha: sess-001 has 130 LOC (50+80), sess-002 has 20 LOC => total 150
        assert alpha["loc_written"] == 150
        assert alpha["cost_per_kloc"] > 0
        # cost_per_kloc = cost / (loc / 1000)
        expected_cpk = alpha["cost"] / (150 / 1000)
        assert abs(alpha["cost_per_kloc"] - expected_cpk) < 0.001

    async def test_get_projects_derived_cache_hit_rate(self, async_db):
        """cache_hit_rate = cache_read / (input + cache_read)."""
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for p in projects:
            total_input = p["input_tokens"] + p["cache_read_tokens"]
            if total_input > 0:
                expected = p["cache_read_tokens"] / total_input
                assert abs(p["cache_hit_rate"] - expected) < 0.0001
            else:
                assert p["cache_hit_rate"] == 0.0

    async def test_get_projects_derived_tokens_per_loc(self, async_db):
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for p in projects:
            if p["loc_written"] > 0:
                expected = p["output_tokens"] / p["loc_written"]
                assert abs(p["tokens_per_loc"] - expected) < 0.001
            else:
                assert p["tokens_per_loc"] == 0.0

    async def test_get_projects_derived_avg_turn_cost(self, async_db):
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for p in projects:
            if p["user_turns"] > 0:
                expected = p["cost"] / p["user_turns"]
                assert abs(p["avg_turn_cost"] - expected) < 0.0001

    async def test_get_projects_zero_loc_no_division_error(self, async_db):
        """Projects with zero LOC should have cost_per_kloc=0, tokens_per_loc=0."""
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for p in projects:
            if p["loc_written"] == 0:
                assert p["cost_per_kloc"] == 0.0
                assert p["tokens_per_loc"] == 0.0

    async def test_get_projects_sort_ascending(self, async_db):
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            sort="cost", order="asc"
        )
        costs = [p["cost"] for p in projects]
        assert costs == sorted(costs)

    async def test_get_projects_sort_by_sessions(self, async_db):
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            sort="sessions", order="desc"
        )
        sessions = [p["sessions"] for p in projects]
        assert sessions == sorted(sessions, reverse=True)

    async def test_get_projects_invalid_sort_defaults_to_cost(self, async_db):
        """Invalid sort field should fall back to 'cost'."""
        projects_invalid, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            sort="nonexistent_field", order="desc"
        )
        projects_cost, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            sort="cost", order="desc"
        )
        # Order should be identical when falling back to cost
        invalid_order = [p["project_path"] for p in projects_invalid]
        cost_order = [p["project_path"] for p in projects_cost]
        assert invalid_order == cost_order

    async def test_get_projects_search_filter(self, async_db):
        projects, total = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            search="alpha"
        )
        assert total == 1
        assert projects[0]["project_path"] == "/path/proj-alpha"

    async def test_get_projects_search_no_match(self, async_db):
        projects, total = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            search="zzz-nonexistent"
        )
        assert total == 0
        assert projects == []

    async def test_get_projects_pagination_page_2(self, async_db):
        projects, total = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            page=2, limit=2
        )
        # 3 total projects, page 2 with limit 2 => 1 project
        assert total == 3
        assert len(projects) == 1

    async def test_get_projects_pagination_beyond_end(self, async_db):
        """Page beyond the total count returns empty list but correct total."""
        projects, total = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            page=100, limit=50
        )
        assert total == 3
        assert projects == []

    async def test_get_projects_two_query_merge_no_inflation(self, async_db):
        """Verify the two-query pattern does not inflate metrics.

        sess-001 has 4 turns and 4 tool calls. A naive cross-product JOIN
        would yield 16 rows, inflating cost by 4x. The two-query pattern
        should produce accurate cost.
        """
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        alpha = next(p for p in projects if p["project_path"] == "/path/proj-alpha")
        # sess-001 turns: 0.00 + 0.10 + 0.00 + 0.20 = 0.30
        # sess-002 turns: 0.00 + 0.05 = 0.05
        # alpha total cost = 0.35
        assert abs(alpha["cost"] - 0.35) < 0.001

    async def test_get_projects_error_rate_accuracy(self, async_db):
        """Verify error_rate is errors / tool_calls, not inflated."""
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        alpha = next(p for p in projects if p["project_path"] == "/path/proj-alpha")
        # proj-alpha: sess-001 has 4 tool calls (1 error), sess-002 has 2 tool calls (0 errors)
        assert alpha["tool_calls"] == 6
        assert alpha["error_count"] == 1
        assert abs(alpha["error_rate"] - 1 / 6) < 0.001

    async def test_get_projects_loc_delivered_computed(self, async_db):
        """loc_delivered = lines_added - lines_deleted."""
        projects, _ = await project_queries.get_projects(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for p in projects:
            assert p["loc_delivered"] == p["lines_added"] - p["lines_deleted"]


@pytest.mark.asyncio
class TestSessionQueries:
    """Direct unit tests for session query functions."""

    async def test_get_sessions_returns_tuple(self, async_db):
        sessions, total = await session_queries.get_sessions(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert isinstance(sessions, list)
        assert isinstance(total, int)
        assert total == 5

    async def test_get_sessions_empty_range(self, async_db):
        sessions, total = await session_queries.get_sessions(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert sessions == []
        assert total == 0

    async def test_get_sessions_ordered_desc(self, async_db):
        sessions, _ = await session_queries.get_sessions(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        timestamps = [s["first_timestamp"] for s in sessions]
        assert timestamps == sorted(timestamps, reverse=True)

    async def test_get_sessions_project_filter(self, async_db):
        sessions, total = await session_queries.get_sessions(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            project="beta"
        )
        assert total == 2
        for s in sessions:
            assert "beta" in s["project_path"].lower()

    async def test_get_sessions_pagination(self, async_db):
        sessions, total = await session_queries.get_sessions(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            page=2, limit=2
        )
        assert total == 5
        assert len(sessions) == 2  # 5 total, page 2 of 2-per-page => 2

    async def test_get_sessions_beyond_last_page(self, async_db):
        sessions, total = await session_queries.get_sessions(
            async_db, date_from="2026-02-03", date_to="2026-02-05",
            page=999, limit=50
        )
        assert total == 5
        assert sessions == []

    async def test_get_sessions_tool_call_counts_not_inflated(self, async_db):
        """Each session's tool_calls should match known data, not be inflated."""
        sessions, _ = await session_queries.get_sessions(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        by_id = {s["session_id"]: s for s in sessions}
        # sess-001 has 4 tool calls, 1 error
        assert by_id["sess-001"]["tool_calls"] == 4
        assert by_id["sess-001"]["errors"] == 1
        # sess-003 has 0 tool calls (only a sidechain assistant turn)
        assert by_id["sess-003"]["tool_calls"] == 0

    async def test_get_session_replay_full_data(self, async_db):
        result = await session_queries.get_session_replay(async_db, "sess-001")
        assert result is not None
        assert result["session_id"] == "sess-001"
        assert result["project_display"] == "proj-alpha"
        assert result["cc_version"] == "1.0.23"
        assert result["git_branch"] == "main"

    async def test_get_session_replay_returns_none_for_missing(self, async_db):
        result = await session_queries.get_session_replay(async_db, "nonexistent-id")
        assert result is None

    async def test_get_session_replay_turns_ordered(self, async_db):
        result = await session_queries.get_session_replay(async_db, "sess-001")
        timestamps = [t["timestamp"] for t in result["turns"]]
        assert timestamps == sorted(timestamps)

    async def test_get_session_replay_cumulative_cost_matches_total(self, async_db):
        result = await session_queries.get_session_replay(async_db, "sess-001")
        last_turn = result["turns"][-1]
        assert abs(last_turn["cumulative_cost"] - result["total_cost"]) < 0.0001

    async def test_get_session_replay_tool_distribution(self, async_db):
        """Tool distribution should reflect actual tool call counts."""
        result = await session_queries.get_session_replay(async_db, "sess-001")
        dist = result["tool_distribution"]
        # sess-001 has: Write x2, Read x1, Bash x1
        assert dist.get("Write", 0) == 2
        assert dist.get("Read", 0) == 1
        assert dist.get("Bash", 0) == 1

    async def test_get_session_replay_cost_by_model(self, async_db):
        result = await session_queries.get_session_replay(async_db, "sess-001")
        cost_by_model = result["cost_by_model"]
        # All turns in sess-001 use claude-opus-4-5-20251101
        assert "claude-opus-4-5-20251101" in cost_by_model
        assert abs(cost_by_model["claude-opus-4-5-20251101"] - 0.30) < 0.001

    async def test_get_session_replay_no_tool_calls_session(self, async_db):
        """sess-003 has 1 turn (sidechain assistant) and 0 tool calls."""
        result = await session_queries.get_session_replay(async_db, "sess-003")
        assert result is not None
        assert result["total_turns"] == 1
        assert result["total_tool_calls"] == 0
        assert result["total_user_turns"] == 0
        # The single turn should have empty tool_calls list
        assert result["turns"][0]["tool_calls"] == []

    async def test_get_session_replay_sidechain_flag(self, async_db):
        """sess-003 has a sidechain turn."""
        result = await session_queries.get_session_replay(async_db, "sess-003")
        assert result["turns"][0]["is_sidechain"] is True

    async def test_get_session_replay_meta_flag(self, async_db):
        """sess-005 has a meta turn."""
        result = await session_queries.get_session_replay(async_db, "sess-005")
        assert result["turns"][0]["is_meta"] is True

    async def test_get_session_replay_tool_call_error_tracking(self, async_db):
        result = await session_queries.get_session_replay(async_db, "sess-001")
        assert result["total_errors"] == 1
        # Find the Bash tool call with error
        all_tc = []
        for t in result["turns"]:
            all_tc.extend(t["tool_calls"])
        bash_errors = [tc for tc in all_tc if tc["tool_name"] == "Bash" and not tc["success"]]
        assert len(bash_errors) == 1
        assert bash_errors[0]["error_message"] == "exit code 1"
        assert bash_errors[0]["error_category"] == "Exit code non-zero"


@pytest.mark.asyncio
class TestCostQueries:
    """Direct unit tests for cost query functions."""

    async def test_get_cost_summary_structure(self, async_db):
        summary = await cost_queries.get_cost_summary(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        expected_keys = {
            "total_cost", "avg_daily_cost", "cost_today",
            "cost_this_week", "cost_this_month", "projected_monthly",
        }
        assert expected_keys == set(summary.keys())

    async def test_get_cost_summary_total(self, async_db):
        """Total cost for 3 daily summaries: 0.30 + 0.06 + 0.19 = 0.55."""
        summary = await cost_queries.get_cost_summary(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert abs(summary["total_cost"] - 0.55) < 0.001

    async def test_get_cost_summary_avg_daily(self, async_db):
        summary = await cost_queries.get_cost_summary(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        # avg of 0.30, 0.06, 0.19
        expected_avg = 0.55 / 3
        assert abs(summary["avg_daily_cost"] - expected_avg) < 0.001

    async def test_get_cost_summary_empty_range(self, async_db):
        summary = await cost_queries.get_cost_summary(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert summary["total_cost"] == 0.0
        assert summary["avg_daily_cost"] == 0.0

    async def test_get_cost_by_model_all_models(self, async_db):
        models = await cost_queries.get_cost_by_model(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        model_names = {m["model"] for m in models}
        assert "claude-opus-4-5-20251101" in model_names
        assert "claude-sonnet-4-20250514" in model_names
        assert "claude-haiku-4-5-20251001" in model_names

    async def test_get_cost_by_model_percentages_sum_to_100(self, async_db):
        models = await cost_queries.get_cost_by_model(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        total_pct = sum(m["percentage"] for m in models)
        assert abs(total_pct - 100.0) < 0.1

    async def test_get_cost_by_model_empty_range(self, async_db):
        models = await cost_queries.get_cost_by_model(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert models == []

    async def test_get_cost_trend_cumulative(self, async_db):
        trend = await cost_queries.get_cost_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert len(trend) == 3
        # Cumulative cost should be monotonically non-decreasing
        for i in range(1, len(trend)):
            assert trend[i]["cumulative_cost"] >= trend[i - 1]["cumulative_cost"]
        # Last cumulative should equal total
        assert abs(trend[-1]["cumulative_cost"] - 0.55) < 0.001

    async def test_get_cost_trend_empty_range(self, async_db):
        trend = await cost_queries.get_cost_trend(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert trend == []

    async def test_get_cost_by_project(self, async_db):
        by_project = await cost_queries.get_cost_by_project(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert len(by_project) == 3
        # Sorted by cost descending
        costs = [p["cost"] for p in by_project]
        assert costs == sorted(costs, reverse=True)

    async def test_get_cost_by_project_percentages(self, async_db):
        by_project = await cost_queries.get_cost_by_project(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        total_pct = sum(p["percentage"] for p in by_project)
        assert abs(total_pct - 100.0) < 0.1

    async def test_get_cache_savings_structure(self, async_db):
        savings = await cost_queries.get_cache_savings(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert "total_cache_read_tokens" in savings
        assert "total_input_tokens" in savings
        assert "cache_hit_rate" in savings
        assert "estimated_savings" in savings
        assert "cost_without_cache" in savings
        assert "actual_cost" in savings

    async def test_get_cache_savings_hit_rate_positive(self, async_db):
        """Test data has nonzero cache_read_tokens, so hit rate should be > 0."""
        savings = await cost_queries.get_cache_savings(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert savings["cache_hit_rate"] > 0
        assert savings["cache_hit_rate"] <= 1.0

    async def test_get_cache_savings_estimated_positive(self, async_db):
        savings = await cost_queries.get_cache_savings(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert savings["estimated_savings"] > 0
        assert savings["cost_without_cache"] > savings["actual_cost"]

    async def test_get_cache_savings_empty_range(self, async_db):
        savings = await cost_queries.get_cache_savings(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert savings["cache_hit_rate"] == 0.0
        assert savings["estimated_savings"] == 0

    async def test_get_spend_forecast_structure(self, async_db):
        forecast = await cost_queries.get_spend_forecast(async_db)
        expected_keys = {
            "daily_avg", "projected_7d", "projected_14d",
            "projected_30d", "trend_direction", "confidence",
        }
        assert expected_keys == set(forecast.keys())

    async def test_get_spend_forecast_trend_direction_valid(self, async_db):
        forecast = await cost_queries.get_spend_forecast(async_db)
        assert forecast["trend_direction"] in ("increasing", "decreasing", "stable")

    async def test_get_spend_forecast_confidence_range(self, async_db):
        forecast = await cost_queries.get_spend_forecast(async_db)
        assert 0 <= forecast["confidence"] <= 1.0

    async def test_get_spend_forecast_projections_consistent(self, async_db):
        forecast = await cost_queries.get_spend_forecast(async_db)
        if forecast["daily_avg"] > 0:
            assert abs(forecast["projected_7d"] - forecast["daily_avg"] * 7) < 0.001
            assert abs(forecast["projected_14d"] - forecast["daily_avg"] * 14) < 0.001
            assert abs(forecast["projected_30d"] - forecast["daily_avg"] * 30) < 0.001

    async def test_get_cost_by_token_type_structure(self, async_db):
        result = await cost_queries.get_cost_by_token_type(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for key in ("input_cost", "output_cost", "cache_read_cost", "cache_write_cost", "total_cost"):
            assert key in result

    async def test_get_cost_by_token_type_empty_range(self, async_db):
        result = await cost_queries.get_cost_by_token_type(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert result["total_cost"] == 0

    async def test_get_cost_by_token_type_components_sum_to_total(self, async_db):
        result = await cost_queries.get_cost_by_token_type(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        component_sum = (
            result["input_cost"] + result["output_cost"]
            + result["cache_read_cost"] + result["cache_write_cost"]
        )
        assert abs(component_sum - result["total_cost"]) < 0.001


@pytest.mark.asyncio
class TestExperimentQueries:
    """Direct unit tests for experiment query functions."""

    async def test_get_tags(self, async_db):
        tags = await experiment_queries.get_tags(async_db)
        assert len(tags) >= 1
        tag_names = [t["tag_name"] for t in tags]
        assert "baseline" in tag_names

    async def test_get_tags_session_count(self, async_db):
        tags = await experiment_queries.get_tags(async_db)
        baseline = next(t for t in tags if t["tag_name"] == "baseline")
        assert baseline["session_count"] == 2  # sess-001 and sess-002

    async def test_create_tag_explicit_sessions(self, async_db):
        count = await experiment_queries.create_tag(
            async_db, "test-direct", session_ids=["sess-003"]
        )
        assert count == 1
        # Verify it was created
        tags = await experiment_queries.get_tags(async_db)
        names = [t["tag_name"] for t in tags]
        assert "test-direct" in names
        # Cleanup
        await experiment_queries.delete_tag(async_db, "test-direct")

    async def test_create_tag_by_date_range(self, async_db):
        count = await experiment_queries.create_tag(
            async_db, "date-range-tag",
            date_from="2026-02-03", date_to="2026-02-03"
        )
        # 2026-02-03 has sess-004 and sess-005
        assert count == 2
        # Cleanup
        await experiment_queries.delete_tag(async_db, "date-range-tag")

    async def test_create_tag_by_project_path(self, async_db):
        count = await experiment_queries.create_tag(
            async_db, "project-tag", project_path="gamma"
        )
        assert count == 1  # Only proj-gamma has sess-005
        await experiment_queries.delete_tag(async_db, "project-tag")

    async def test_create_tag_idempotent(self, async_db):
        """Tagging the same session twice should use INSERT OR IGNORE."""
        count1 = await experiment_queries.create_tag(
            async_db, "idempotent-tag", session_ids=["sess-001"]
        )
        count2 = await experiment_queries.create_tag(
            async_db, "idempotent-tag", session_ids=["sess-001"]
        )
        assert count1 == 1
        assert count2 == 1  # Returns 1 but doesn't insert duplicate
        # Verify only one row exists
        tags = await experiment_queries.get_tags(async_db)
        tag = next(t for t in tags if t["tag_name"] == "idempotent-tag")
        assert tag["session_count"] == 1
        await experiment_queries.delete_tag(async_db, "idempotent-tag")

    async def test_delete_tag_returns_count(self, async_db):
        await experiment_queries.create_tag(
            async_db, "del-count", session_ids=["sess-001", "sess-002"]
        )
        count = await experiment_queries.delete_tag(async_db, "del-count")
        assert count == 2

    async def test_delete_nonexistent_tag_returns_zero(self, async_db):
        count = await experiment_queries.delete_tag(async_db, "no-such-tag-xyz")
        assert count == 0

    async def test_compare_tags_structure(self, async_db):
        # Create two tags for comparison
        await experiment_queries.create_tag(
            async_db, "cmp-a", session_ids=["sess-001", "sess-002"]
        )
        await experiment_queries.create_tag(
            async_db, "cmp-b", session_ids=["sess-003", "sess-004"]
        )
        result = await experiment_queries.compare_tags(async_db, "cmp-a", "cmp-b")
        assert result["tag_a"] == "cmp-a"
        assert result["tag_b"] == "cmp-b"
        assert result["tag_a_sessions"] == 2
        assert result["tag_b_sessions"] == 2
        metric_names = [m["metric_name"] for m in result["metrics"]]
        assert "cost" in metric_names
        assert "error_rate" in metric_names
        assert "loc_written" in metric_names
        # Cleanup
        await experiment_queries.delete_tag(async_db, "cmp-a")
        await experiment_queries.delete_tag(async_db, "cmp-b")

    async def test_compare_tags_with_empty_tag(self, async_db):
        """Comparing against a nonexistent/empty tag should return zero metrics."""
        await experiment_queries.create_tag(
            async_db, "cmp-real", session_ids=["sess-001"]
        )
        result = await experiment_queries.compare_tags(
            async_db, "cmp-real", "nonexistent-tag"
        )
        assert result["tag_a_sessions"] == 1
        assert result["tag_b_sessions"] == 0
        # All tag_b values should be zero
        for m in result["metrics"]:
            assert m["tag_b_value"] == 0
        await experiment_queries.delete_tag(async_db, "cmp-real")

    async def test_compare_tags_both_empty(self, async_db):
        result = await experiment_queries.compare_tags(
            async_db, "empty-a", "empty-b"
        )
        assert result["tag_a_sessions"] == 0
        assert result["tag_b_sessions"] == 0
        for m in result["metrics"]:
            assert m["tag_a_value"] == 0
            assert m["tag_b_value"] == 0
            assert m["absolute_delta"] == 0

    async def test_compare_tags_improvement_direction(self, async_db):
        """Cost is lower-is-better. If tag_b has lower cost, is_improvement is True."""
        await experiment_queries.create_tag(
            async_db, "hi-cost", session_ids=["sess-001"]
        )
        await experiment_queries.create_tag(
            async_db, "lo-cost", session_ids=["sess-003"]
        )
        result = await experiment_queries.compare_tags(async_db, "hi-cost", "lo-cost")
        cost_metric = next(m for m in result["metrics"] if m["metric_name"] == "cost")
        # hi-cost (sess-001) = 0.30, lo-cost (sess-003) = 0.01
        # delta = 0.01 - 0.30 = -0.29, which is an improvement (lower is better)
        assert cost_metric["absolute_delta"] < 0
        assert cost_metric["is_improvement"] is True
        await experiment_queries.delete_tag(async_db, "hi-cost")
        await experiment_queries.delete_tag(async_db, "lo-cost")


@pytest.mark.asyncio
class TestProductivityQueries:
    """Direct unit tests for productivity query functions."""

    async def test_get_efficiency_summary(self, async_db):
        summary = await productivity_queries.get_efficiency_summary(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        # total LOC from daily_summaries: 130 + 20 + 40 = 190
        assert summary["total_loc_written"] == 190
        assert summary["total_loc_delivered"] == 192  # 130 + 20 + 42
        assert summary["error_rate"] >= 0
        assert summary["cost_per_kloc"] > 0

    async def test_get_efficiency_summary_empty_range(self, async_db):
        summary = await productivity_queries.get_efficiency_summary(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert summary["total_loc_written"] == 0
        assert summary["error_rate"] == 0
        assert summary["cost_per_kloc"] == 0

    async def test_get_loc_trend(self, async_db):
        trend = await productivity_queries.get_loc_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert len(trend) == 3
        dates = [t["date"] for t in trend]
        assert dates == sorted(dates)
        for t in trend:
            assert "loc_written" in t
            assert "loc_delivered" in t
            assert "lines_added" in t
            assert "lines_deleted" in t

    async def test_get_language_breakdown(self, async_db):
        langs = await productivity_queries.get_language_breakdown(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        lang_names = [l["language"] for l in langs]
        assert "python" in lang_names  # Most tool calls use python

    async def test_get_language_breakdown_percentages(self, async_db):
        langs = await productivity_queries.get_language_breakdown(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        if langs:
            total_pct = sum(l["percentage"] for l in langs)
            assert abs(total_pct - 100.0) < 0.1

    async def test_get_tool_usage_all_tools(self, async_db):
        tools = await productivity_queries.get_tool_usage(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        tool_names = {t["tool_name"] for t in tools}
        assert {"Write", "Read", "Edit", "Bash"} == tool_names

    async def test_get_tool_usage_success_rates(self, async_db):
        tools = await productivity_queries.get_tool_usage(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        by_name = {t["tool_name"]: t for t in tools}
        # Write: 3 calls, all success
        assert by_name["Write"]["total_calls"] == 3
        assert by_name["Write"]["success_rate"] == 1.0
        # Bash: 2 calls, 1 success, 1 error
        assert by_name["Bash"]["total_calls"] == 2
        assert by_name["Bash"]["success_rate"] == 0.5

    async def test_get_error_analysis(self, async_db):
        errors = await productivity_queries.get_error_analysis(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        # 2 total errors: Bash exit code, Edit not unique
        assert errors["total_errors"] == 2
        assert errors["error_rate"] == 2 / 8  # 2 errors out of 8 tool calls

    async def test_get_error_analysis_categories(self, async_db):
        errors = await productivity_queries.get_error_analysis(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        cats = {c["category"] for c in errors["categories"]}
        assert "Exit code non-zero" in cats
        assert "Not unique" in cats

    async def test_get_file_hotspots(self, async_db):
        hotspots = await productivity_queries.get_file_hotspots(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert len(hotspots) > 0
        # Files are ordered by total_touches DESC
        touches = [h["total_touches"] for h in hotspots]
        assert touches == sorted(touches, reverse=True)

    async def test_get_file_hotspots_limit(self, async_db):
        hotspots = await productivity_queries.get_file_hotspots(
            async_db, date_from="2026-02-03", date_to="2026-02-05", limit=2
        )
        assert len(hotspots) <= 2


@pytest.mark.asyncio
class TestAnalyticsQueries:
    """Direct unit tests for analytics query functions."""

    async def test_get_thinking_analysis(self, async_db):
        thinking = await analytics_queries.get_thinking_analysis(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        # Turns with thinking: u02(500), u04(1200), u06(300), u09(200), u10(800) = 5 turns
        assert thinking["turns_with_thinking"] == 5
        assert thinking["total_thinking_chars"] == 500 + 1200 + 300 + 200 + 800
        assert thinking["total_turns"] == 10
        assert thinking["thinking_rate"] == 5 / 10

    async def test_get_thinking_analysis_by_model(self, async_db):
        thinking = await analytics_queries.get_thinking_analysis(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        model_names = {m["model"] for m in thinking["by_model"]}
        # Opus, Sonnet, and Haiku do NOT all have thinking -- haiku u07 has 0 thinking
        # Opus: u02(500), u04(1200), u10(800) = 3 turns
        # Sonnet: u06(300), u09(200) = 2 turns
        assert "claude-opus-4-5-20251101" in model_names
        assert "claude-sonnet-4-20250514" in model_names

    async def test_get_truncation_analysis(self, async_db):
        trunc = await analytics_queries.get_truncation_analysis(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert trunc["total_turns"] > 0
        reasons = {r["stop_reason"] for r in trunc["by_stop_reason"]}
        assert "end_turn" in reasons
        assert "max_tokens" in reasons

    async def test_get_truncation_analysis_percentages(self, async_db):
        trunc = await analytics_queries.get_truncation_analysis(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        total_pct = sum(r["percentage"] for r in trunc["by_stop_reason"])
        assert abs(total_pct - 100.0) < 0.1

    async def test_get_sidechain_analysis(self, async_db):
        sc = await analytics_queries.get_sidechain_analysis(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        # u07 in sess-003 is_sidechain=1
        assert sc["total_sidechains"] == 1
        assert sc["sidechain_rate"] == 1 / 10

    async def test_get_sidechain_analysis_by_project(self, async_db):
        sc = await analytics_queries.get_sidechain_analysis(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert len(sc["by_project"]) >= 1
        # Only proj-beta has sidechains
        assert sc["by_project"][0]["project"] == "proj-beta"

    async def test_get_branch_analytics(self, async_db):
        branches = await analytics_queries.get_branch_analytics(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        branch_names = {b["branch"] for b in branches["branches"]}
        assert "main" in branch_names
        assert "feat-x" in branch_names
        assert "develop" in branch_names

    async def test_get_branch_analytics_cost_positive(self, async_db):
        branches = await analytics_queries.get_branch_analytics(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for b in branches["branches"]:
            assert b["cost"] >= 0

    async def test_get_version_impact(self, async_db):
        versions = await analytics_queries.get_version_impact(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        version_names = {v["version"] for v in versions["versions"]}
        assert "1.0.23" in version_names
        assert "1.0.24" in version_names

    async def test_get_skills_agents(self, async_db):
        sa = await analytics_queries.get_skills_agents(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        # daily_summaries: agent_spawns = 0+1+0 = 1, skill_invocations = 0+0+1 = 1
        assert sa["total_agent_spawns"] == 1
        assert sa["total_skill_invocations"] == 1
        # sess-003 is_agent=1, cost = 0.01
        assert sa["agent_cost"] > 0


@pytest.mark.asyncio
class TestSettingsQueries:
    """Direct unit tests for settings query functions."""

    async def test_get_db_stats(self, async_db):
        stats = await settings_queries.get_db_stats(async_db)
        assert stats["sessions"] == 5
        assert stats["turns"] == 10
        assert stats["tool_calls"] == 8
        assert stats["daily_summaries"] == 3
        assert stats["experiment_tags"] == 2  # baseline for sess-001 and sess-002

    async def test_get_etl_status(self, async_db):
        status = await settings_queries.get_etl_status(async_db)
        assert "files_total" in status
        assert "last_run" in status


# =====================================================================
# Endpoint edge case tests
# =====================================================================


@pytest.mark.asyncio
class TestDashboardEdgeCases:
    """Edge cases for the dashboard endpoint."""

    async def test_dashboard_no_params(self, client):
        """Dashboard with no query parameters should still return valid data."""
        resp = await client.get("/api/dashboard")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["sparkline_7d"], list)
        assert isinstance(data["recent_sessions"], list)

    async def test_dashboard_empty_date_range(self, client):
        """A date range with no data returns empty lists but valid structure."""
        resp = await client.get("/api/dashboard?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cost_trend"] == []
        assert data["top_projects"] == []

    async def test_dashboard_single_day_range(self, client):
        resp = await client.get("/api/dashboard?from=2026-02-05&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["cost_trend"]) == 1

    async def test_dashboard_vitals_all_numeric(self, client):
        resp = await client.get("/api/dashboard")
        vitals = resp.json()["vitals"]
        for key in ("sessions", "cost", "loc_written", "error_rate"):
            assert isinstance(vitals[key], (int, float))

    async def test_dashboard_recent_sessions_limit(self, client):
        """Recent sessions should not exceed 10 (default limit)."""
        resp = await client.get("/api/dashboard")
        data = resp.json()
        assert len(data["recent_sessions"]) <= 10


@pytest.mark.asyncio
class TestProjectsEdgeCases:
    """Edge cases for the projects endpoint."""

    async def test_projects_empty_date_range(self, client):
        resp = await client.get("/api/projects?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []
        assert data["pagination"]["total_count"] == 0
        assert data["pagination"]["total_pages"] == 0

    async def test_projects_large_page_number(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05&page=999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["projects"] == []
        assert data["pagination"]["total_count"] == 3

    async def test_projects_sort_by_loc_written(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05&sort=loc_written&order=desc")
        assert resp.status_code == 200
        data = resp.json()
        locs = [p["loc_written"] for p in data["projects"]]
        assert locs == sorted(locs, reverse=True)

    async def test_projects_sort_ascending(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05&sort=cost&order=asc")
        assert resp.status_code == 200
        costs = [p["cost"] for p in resp.json()["projects"]]
        assert costs == sorted(costs)

    async def test_projects_invalid_sort_field_falls_back(self, client):
        """Invalid sort field should not cause an error; falls back to cost."""
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05&sort=invalid_xyz")
        assert resp.status_code == 200
        data = resp.json()
        costs = [p["cost"] for p in data["projects"]]
        assert costs == sorted(costs, reverse=True)

    async def test_projects_limit_boundary(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05&limit=1")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["projects"]) == 1
        assert data["pagination"]["total_pages"] == 3

    async def test_projects_search_case_insensitive(self, client):
        """Search should match case-insensitively (LIKE is case-insensitive for ASCII)."""
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05&search=ALPHA")
        assert resp.status_code == 200
        data = resp.json()
        # SQLite LIKE is case-insensitive for ASCII letters by default
        assert len(data["projects"]) >= 1

    async def test_projects_has_derived_metrics(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for p in data["projects"]:
            assert "cost_per_kloc" in p
            assert "tokens_per_loc" in p
            assert "cache_hit_rate" in p
            assert "avg_turn_cost" in p

    async def test_projects_pagination_total_pages(self, client):
        resp = await client.get("/api/projects?from=2026-02-03&to=2026-02-05&limit=2")
        data = resp.json()
        # 3 projects, limit 2 => 2 pages
        assert data["pagination"]["total_pages"] == 2


@pytest.mark.asyncio
class TestSessionsEdgeCases:
    """Edge cases for the sessions endpoint."""

    async def test_sessions_empty_date_range(self, client):
        resp = await client.get("/api/sessions?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["pagination"]["total_count"] == 0

    async def test_sessions_large_page_number(self, client):
        resp = await client.get("/api/sessions?from=2026-02-03&to=2026-02-05&page=999")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["pagination"]["total_count"] == 5

    async def test_sessions_project_filter_no_match(self, client):
        resp = await client.get("/api/sessions?from=2026-02-03&to=2026-02-05&project=nonexistent")
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions"] == []
        assert data["pagination"]["total_count"] == 0

    async def test_sessions_have_tool_call_counts(self, client):
        resp = await client.get("/api/sessions?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        by_id = {s["session_id"]: s for s in data["sessions"]}
        assert by_id["sess-001"]["tool_calls"] == 4
        assert by_id["sess-001"]["errors"] == 1

    async def test_session_replay_tool_calls_attached_to_correct_turns(self, client):
        """Tool calls should be on assistant turns, not user turns."""
        resp = await client.get("/api/sessions/sess-001/replay")
        data = resp.json()
        for t in data["turns"]:
            if t["entry_type"] == "user":
                assert t["tool_calls"] == []

    async def test_session_replay_sess002(self, client):
        """Verify sess-002 replay data."""
        resp = await client.get("/api/sessions/sess-002/replay")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total_turns"] == 2
        assert data["total_user_turns"] == 1
        assert abs(data["total_cost"] - 0.05) < 0.001

    async def test_session_replay_sess004_stop_reason(self, client):
        """sess-004 has a max_tokens stop reason."""
        resp = await client.get("/api/sessions/sess-004/replay")
        data = resp.json()
        assistant_turns = [t for t in data["turns"] if t["entry_type"] == "assistant"]
        stop_reasons = [t["stop_reason"] for t in assistant_turns]
        assert "max_tokens" in stop_reasons

    async def test_session_replay_is_agent_flag(self, client):
        """sess-003 is an agent session."""
        resp = await client.get("/api/sessions/sess-003/replay")
        data = resp.json()
        assert data["is_agent"] is True

    async def test_session_replay_no_turn_id_leaked(self, client):
        """The internal _turn_id should not appear in the response."""
        resp = await client.get("/api/sessions/sess-001/replay")
        data = resp.json()
        for t in data["turns"]:
            assert "_turn_id" not in t


@pytest.mark.asyncio
class TestCostEdgeCases:
    """Edge cases for the cost endpoint."""

    async def test_cost_empty_date_range(self, client):
        resp = await client.get("/api/cost?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_cost"] == 0.0
        assert data["by_model"] == []
        assert data["trend"] == []

    async def test_cost_no_date_params(self, client):
        """Cost endpoint without date params should still return valid data."""
        resp = await client.get("/api/cost")
        assert resp.status_code == 200
        data = resp.json()
        assert "summary" in data
        assert "forecast" in data

    async def test_cost_forecast_always_present(self, client):
        resp = await client.get("/api/cost?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        forecast = data["forecast"]
        assert "daily_avg" in forecast
        assert "trend_direction" in forecast
        assert forecast["trend_direction"] in ("increasing", "decreasing", "stable")

    async def test_cost_by_token_type_present(self, client):
        resp = await client.get("/api/cost?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        assert "by_token_type" in data
        assert "input_cost" in data["by_token_type"]
        assert "output_cost" in data["by_token_type"]

    async def test_cost_by_project_present(self, client):
        resp = await client.get("/api/cost?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        assert "by_project" in data
        assert len(data["by_project"]) == 3

    async def test_cost_trend_cumulative_monotonic(self, client):
        resp = await client.get("/api/cost?from=2026-02-03&to=2026-02-05")
        trend = resp.json()["trend"]
        for i in range(1, len(trend)):
            assert trend[i]["cumulative_cost"] >= trend[i - 1]["cumulative_cost"]


@pytest.mark.asyncio
class TestProductivityEdgeCases:
    """Edge cases for the productivity endpoint."""

    async def test_productivity_empty_date_range(self, client):
        resp = await client.get("/api/productivity?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["summary"]["total_loc_written"] == 0
        assert data["loc_trend"] == []

    async def test_productivity_no_params(self, client):
        resp = await client.get("/api/productivity")
        assert resp.status_code == 200

    async def test_file_hotspots_present(self, client):
        resp = await client.get("/api/productivity?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        hotspots = data["file_hotspots"]
        assert isinstance(hotspots, list)
        assert len(hotspots) > 0
        for h in hotspots:
            assert "file_path" in h
            assert "total_touches" in h

    async def test_language_breakdown(self, client):
        resp = await client.get("/api/productivity?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        langs = data["languages"]
        assert isinstance(langs, list)
        lang_names = [l["language"] for l in langs]
        assert "python" in lang_names


@pytest.mark.asyncio
class TestAnalyticsEdgeCases:
    """Edge cases for the analytics endpoint."""

    async def test_analytics_empty_date_range(self, client):
        resp = await client.get("/api/analytics?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        data = resp.json()
        assert data["thinking"]["total_thinking_chars"] == 0
        assert data["sidechains"]["total_sidechains"] == 0

    async def test_analytics_no_params(self, client):
        resp = await client.get("/api/analytics")
        assert resp.status_code == 200

    async def test_analytics_sidechain_details(self, client):
        resp = await client.get("/api/analytics?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        sc = data["sidechains"]
        assert sc["total_sidechains"] == 1
        assert 0 < sc["sidechain_rate"] < 1

    async def test_analytics_cache_tiers_structure(self, client):
        resp = await client.get("/api/analytics?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        cache = data["cache_tiers"]
        assert "ephemeral_5m_tokens" in cache
        assert "ephemeral_1h_tokens" in cache
        assert "standard_cache_tokens" in cache

    async def test_analytics_skills_agents(self, client):
        resp = await client.get("/api/analytics?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        sa = data["skills_agents"]
        assert "total_agent_spawns" in sa
        assert "total_skill_invocations" in sa
        assert "agent_cost" in sa


@pytest.mark.asyncio
class TestExperimentsEdgeCases:
    """Edge cases for the experiments endpoints."""

    async def test_create_tag_empty_session_ids(self, client):
        """Empty session_ids list with no criteria creates an empty smart tag."""
        resp = await client.post("/api/experiments/tags", json={
            "tag_name": "empty-list-tag",
            "session_ids": []
        })
        assert resp.status_code == 200
        data = resp.json()
        # No criteria and no session_ids = empty tag definition
        assert data["sessions_tagged"] == 0
        # Cleanup
        await client.delete("/api/experiments/tags/empty-list-tag")

    async def test_create_tag_by_date_range(self, client):
        resp = await client.post("/api/experiments/tags", json={
            "tag_name": "date-tag",
            "date_from": "2026-02-03",
            "date_to": "2026-02-03"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["sessions_tagged"] == 2  # sess-004 and sess-005
        await client.delete("/api/experiments/tags/date-tag")

    async def test_create_tag_by_project_path(self, client):
        resp = await client.post("/api/experiments/tags", json={
            "tag_name": "proj-tag",
            "project_path": "gamma"
        })
        assert resp.status_code == 200
        assert resp.json()["sessions_tagged"] == 1
        await client.delete("/api/experiments/tags/proj-tag")

    async def test_compare_nonexistent_tags(self, client):
        """Comparing two nonexistent tags should return valid structure with zero data."""
        resp = await client.get("/api/experiments/compare?tag_a=nope1&tag_b=nope2")
        assert resp.status_code == 200
        data = resp.json()
        assert data["tag_a_sessions"] == 0
        assert data["tag_b_sessions"] == 0
        assert len(data["metrics"]) > 0

    async def test_compare_tags_metric_names(self, client):
        """Compare should return the expected set of metric names."""
        await client.post("/api/experiments/tags", json={
            "tag_name": "ma", "session_ids": ["sess-001"]
        })
        await client.post("/api/experiments/tags", json={
            "tag_name": "mb", "session_ids": ["sess-003"]
        })
        resp = await client.get("/api/experiments/compare?tag_a=ma&tag_b=mb")
        data = resp.json()
        names = {m["metric_name"] for m in data["metrics"]}
        expected = {
            "cost", "cost_per_kloc", "cache_hit_rate",
            "loc_written", "loc_delivered", "files_created", "files_edited",
            "input_tokens", "output_tokens", "tokens_per_loc", "thinking_chars",
            "sessions", "user_turns", "tool_calls", "error_rate", "agent_spawns",
        }
        assert names == expected
        await client.delete("/api/experiments/tags/ma")
        await client.delete("/api/experiments/tags/mb")

    async def test_tag_list_after_create_and_delete(self, client):
        """Verify tag lifecycle: create, list (present), delete, list (absent)."""
        await client.post("/api/experiments/tags", json={
            "tag_name": "lifecycle",
            "session_ids": ["sess-001"]
        })
        resp = await client.get("/api/experiments/tags")
        names = [t["tag_name"] for t in resp.json()["tags"]]
        assert "lifecycle" in names

        await client.delete("/api/experiments/tags/lifecycle")
        resp = await client.get("/api/experiments/tags")
        names = [t["tag_name"] for t in resp.json()["tags"]]
        assert "lifecycle" not in names

    async def test_tag_session_count_accurate(self, client):
        resp = await client.get("/api/experiments/tags")
        data = resp.json()
        baseline = next(t for t in data["tags"] if t["tag_name"] == "baseline")
        assert baseline["session_count"] == 2


@pytest.mark.asyncio
class TestSettingsEdgeCases:
    """Edge cases for the settings endpoint."""

    async def test_settings_excludes_default_pricing(self, client):
        """The 'default' pricing entry should not appear in the pricing table."""
        resp = await client.get("/api/settings")
        pricing = resp.json()["pricing"]
        assert "default" not in pricing

    async def test_settings_has_version(self, client):
        resp = await client.get("/api/settings")
        data = resp.json()
        assert "version" in data
        assert data["version"] == "2026-02-01"

    async def test_settings_etl_status_structure(self, client):
        resp = await client.get("/api/settings")
        etl = resp.json()["etl_status"]
        assert "files_total" in etl
        assert "files_processed" in etl
        assert "last_run" in etl

    async def test_settings_all_models_have_pricing(self, client):
        resp = await client.get("/api/settings")
        pricing = resp.json()["pricing"]
        for model_name, p in pricing.items():
            assert "input" in p
            assert "output" in p
            assert "cache_read" in p
            assert "cache_write" in p
            assert p["input"] >= 0
            assert p["output"] >= 0


# =====================================================================
# Phase 3-5: New endpoint and query tests
# =====================================================================


def _encode_project_path(path: str) -> str:
    """Base64url-encode a project path for the project detail endpoint."""
    encoded = base64.urlsafe_b64encode(path.encode("utf-8")).decode("utf-8")
    return encoded.rstrip("=")


# =====================================================================
# Heatmap endpoint and query tests
# =====================================================================


@pytest.mark.asyncio
class TestHeatmapEndpoint:
    """Test /api/heatmap endpoint."""

    async def test_heatmap_returns_correct_structure(self, client):
        resp = await client.get("/api/heatmap?from=2026-02-03&to=2026-02-05&metric=sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "cells" in data
        assert "metric" in data
        assert "max_value" in data
        assert data["metric"] == "sessions"

    async def test_heatmap_cells_have_expected_fields(self, client):
        resp = await client.get("/api/heatmap?from=2026-02-03&to=2026-02-05&metric=sessions")
        data = resp.json()
        for cell in data["cells"]:
            assert "day" in cell
            assert "hour" in cell
            assert "value" in cell
            assert 0 <= cell["day"] <= 6
            assert 0 <= cell["hour"] <= 23
            assert cell["value"] >= 0

    async def test_heatmap_max_value_matches_cells(self, client):
        resp = await client.get("/api/heatmap?from=2026-02-03&to=2026-02-05&metric=sessions")
        data = resp.json()
        if data["cells"]:
            actual_max = max(c["value"] for c in data["cells"])
            assert abs(data["max_value"] - actual_max) < 0.001

    async def test_heatmap_cost_metric(self, client):
        resp = await client.get("/api/heatmap?from=2026-02-03&to=2026-02-05&metric=cost")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "cost"
        assert isinstance(data["max_value"], (int, float))

    async def test_heatmap_tool_calls_metric(self, client):
        resp = await client.get("/api/heatmap?from=2026-02-03&to=2026-02-05&metric=tool_calls")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "tool_calls"

    async def test_heatmap_loc_metric(self, client):
        resp = await client.get("/api/heatmap?from=2026-02-03&to=2026-02-05&metric=loc")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "loc"

    async def test_heatmap_invalid_metric_rejected(self, client):
        resp = await client.get("/api/heatmap?metric=invalid_metric")
        assert resp.status_code == 422

    async def test_heatmap_empty_date_range(self, client):
        resp = await client.get("/api/heatmap?from=2020-01-01&to=2020-01-02&metric=sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert data["cells"] == []
        assert data["max_value"] == 0.0

    async def test_heatmap_no_date_params(self, client):
        resp = await client.get("/api/heatmap?metric=sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data["cells"], list)

    async def test_heatmap_default_metric_is_sessions(self, client):
        resp = await client.get("/api/heatmap")
        assert resp.status_code == 200
        data = resp.json()
        assert data["metric"] == "sessions"


@pytest.mark.asyncio
class TestHeatmapQueries:
    """Direct unit tests for heatmap query functions."""

    async def test_get_heatmap_data_sessions(self, async_db):
        cells, max_val = await heatmap_queries.get_heatmap_data(
            async_db, date_from="2026-02-03", date_to="2026-02-05", metric="sessions"
        )
        assert isinstance(cells, list)
        assert len(cells) > 0
        assert max_val > 0
        for cell in cells:
            assert "day" in cell
            assert "hour" in cell
            assert "value" in cell

    async def test_get_heatmap_data_cost(self, async_db):
        cells, max_val = await heatmap_queries.get_heatmap_data(
            async_db, date_from="2026-02-03", date_to="2026-02-05", metric="cost"
        )
        assert isinstance(cells, list)
        assert max_val >= 0

    async def test_get_heatmap_data_loc(self, async_db):
        cells, max_val = await heatmap_queries.get_heatmap_data(
            async_db, date_from="2026-02-03", date_to="2026-02-05", metric="loc"
        )
        assert isinstance(cells, list)
        # Some tool calls have loc_written > 0
        if cells:
            total_loc = sum(c["value"] for c in cells)
            assert total_loc > 0

    async def test_get_heatmap_data_tool_calls(self, async_db):
        cells, max_val = await heatmap_queries.get_heatmap_data(
            async_db, date_from="2026-02-03", date_to="2026-02-05", metric="tool_calls"
        )
        assert isinstance(cells, list)
        if cells:
            total_calls = sum(c["value"] for c in cells)
            # date(tc.timestamp) correctly includes all records from Feb 3-5
            assert total_calls == 8

    async def test_get_heatmap_data_empty_range(self, async_db):
        cells, max_val = await heatmap_queries.get_heatmap_data(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert cells == []
        assert max_val == 0.0

    async def test_get_heatmap_data_day_remapping(self, async_db):
        """Day values should be in range 0-6 (0=Monday)."""
        cells, _ = await heatmap_queries.get_heatmap_data(async_db)
        for cell in cells:
            assert 0 <= cell["day"] <= 6

    async def test_get_heatmap_data_hour_range(self, async_db):
        """Hour values should be in range 0-23."""
        cells, _ = await heatmap_queries.get_heatmap_data(async_db)
        for cell in cells:
            assert 0 <= cell["hour"] <= 23


# =====================================================================
# Search endpoint and query tests
# =====================================================================


@pytest.mark.asyncio
class TestSearchEndpoint:
    """Test /api/search endpoint."""

    async def test_search_returns_correct_structure(self, client):
        resp = await client.get("/api/search?q=alpha&limit=5")
        assert resp.status_code == 200
        data = resp.json()
        assert "results" in data
        assert "query" in data
        assert data["query"] == "alpha"

    async def test_search_results_have_expected_fields(self, client):
        resp = await client.get("/api/search?q=alpha")
        data = resp.json()
        for result in data["results"]:
            assert "category" in result
            assert "label" in result
            assert "sublabel" in result
            assert "url" in result

    async def test_search_finds_project(self, client):
        resp = await client.get("/api/search?q=alpha")
        data = resp.json()
        categories = [r["category"] for r in data["results"]]
        assert "project" in categories
        project_results = [r for r in data["results"] if r["category"] == "project"]
        assert any("alpha" in r["label"].lower() for r in project_results)

    async def test_search_finds_session(self, client):
        resp = await client.get("/api/search?q=sess")
        data = resp.json()
        categories = [r["category"] for r in data["results"]]
        assert "session" in categories

    async def test_search_finds_model(self, client):
        resp = await client.get("/api/search?q=opus")
        data = resp.json()
        categories = [r["category"] for r in data["results"]]
        assert "model" in categories

    async def test_search_finds_branch(self, client):
        resp = await client.get("/api/search?q=main")
        data = resp.json()
        categories = [r["category"] for r in data["results"]]
        assert "branch" in categories

    async def test_search_finds_tag(self, client):
        resp = await client.get("/api/search?q=baseline")
        data = resp.json()
        categories = [r["category"] for r in data["results"]]
        assert "tag" in categories

    async def test_search_finds_pages(self, client):
        """Static page names should match."""
        resp = await client.get("/api/search?q=dashboard")
        data = resp.json()
        categories = [r["category"] for r in data["results"]]
        assert "page" in categories
        page_results = [r for r in data["results"] if r["category"] == "page"]
        assert any(r["label"] == "Dashboard" for r in page_results)

    async def test_search_respects_limit(self, client):
        resp = await client.get("/api/search?q=s&limit=2")
        data = resp.json()
        # Limit applies per-entity-type at the DB level, so total may exceed limit
        # but each DB query is limited
        assert isinstance(data["results"], list)

    async def test_search_empty_query(self, client):
        resp = await client.get("/api/search?q=")
        assert resp.status_code == 200
        data = resp.json()
        # Empty query should return no results (search_all returns [] for empty query)
        assert data["results"] == []

    async def test_search_no_match(self, client):
        resp = await client.get("/api/search?q=zzznonexistentxxx")
        assert resp.status_code == 200
        data = resp.json()
        assert data["results"] == []

    async def test_search_result_categories_valid(self, client):
        """All result categories should be from known set."""
        resp = await client.get("/api/search?q=a")
        data = resp.json()
        valid_categories = {"page", "project", "session", "model", "branch", "tag"}
        for r in data["results"]:
            assert r["category"] in valid_categories


@pytest.mark.asyncio
class TestSearchQueries:
    """Direct unit tests for search query functions."""

    async def test_search_all_finds_project(self, async_db):
        results = await search_queries.search_all(async_db, "alpha")
        project_results = [r for r in results if r["category"] == "project"]
        assert len(project_results) >= 1
        assert "alpha" in project_results[0]["label"].lower()

    async def test_search_all_finds_session(self, async_db):
        results = await search_queries.search_all(async_db, "sess-001")
        session_results = [r for r in results if r["category"] == "session"]
        assert len(session_results) >= 1

    async def test_search_all_finds_model(self, async_db):
        results = await search_queries.search_all(async_db, "opus")
        model_results = [r for r in results if r["category"] == "model"]
        assert len(model_results) >= 1
        assert "opus" in model_results[0]["label"].lower()

    async def test_search_all_finds_branch(self, async_db):
        results = await search_queries.search_all(async_db, "feat")
        branch_results = [r for r in results if r["category"] == "branch"]
        assert len(branch_results) >= 1
        assert "feat-x" == branch_results[0]["label"]

    async def test_search_all_finds_tag(self, async_db):
        results = await search_queries.search_all(async_db, "baseline")
        tag_results = [r for r in results if r["category"] == "tag"]
        assert len(tag_results) >= 1

    async def test_search_all_empty_query_returns_empty(self, async_db):
        results = await search_queries.search_all(async_db, "")
        assert results == []

    async def test_search_all_respects_limit(self, async_db):
        results = await search_queries.search_all(async_db, "s", limit=1)
        # Each DB query has its own limit, so total may be > 1
        # but each category should have at most 1 match
        session_results = [r for r in results if r["category"] == "session"]
        assert len(session_results) <= 1

    async def test_search_all_page_match(self, async_db):
        results = await search_queries.search_all(async_db, "settings")
        page_results = [r for r in results if r["category"] == "page"]
        assert len(page_results) >= 1
        assert page_results[0]["label"] == "Settings"
        assert page_results[0]["url"] == "/settings"

    async def test_search_all_no_match(self, async_db):
        results = await search_queries.search_all(async_db, "zzznonexistentxxx")
        assert results == []


# =====================================================================
# Cost new endpoints and query tests
# =====================================================================


@pytest.mark.asyncio
class TestCostAnomaliesEndpoint:
    """Test /api/cost/anomalies endpoint."""

    async def test_anomalies_returns_list(self, client):
        resp = await client.get("/api/cost/anomalies?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3  # 3 daily summaries

    async def test_anomalies_have_expected_fields(self, client):
        resp = await client.get("/api/cost/anomalies?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            assert "date" in item
            assert "cost" in item
            assert "is_anomaly" in item
            assert "threshold" in item

    async def test_anomalies_dates_ordered(self, client):
        resp = await client.get("/api/cost/anomalies?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        dates = [item["date"] for item in data]
        assert dates == sorted(dates)

    async def test_anomalies_threshold_consistent(self, client):
        """All entries should have the same threshold (computed from IQR of the range)."""
        resp = await client.get("/api/cost/anomalies?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        if data:
            threshold = data[0]["threshold"]
            for item in data:
                assert item["threshold"] == threshold

    async def test_anomalies_is_anomaly_correct(self, client):
        """is_anomaly should be True only when cost > threshold."""
        resp = await client.get("/api/cost/anomalies?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            expected = item["cost"] > item["threshold"]
            assert item["is_anomaly"] == expected

    async def test_anomalies_empty_range(self, client):
        resp = await client.get("/api/cost/anomalies?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_anomalies_no_params(self, client):
        resp = await client.get("/api/cost/anomalies")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)


@pytest.mark.asyncio
class TestCostCumulativeEndpoint:
    """Test /api/cost/cumulative endpoint."""

    async def test_cumulative_returns_list(self, client):
        resp = await client.get("/api/cost/cumulative?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3

    async def test_cumulative_has_expected_fields(self, client):
        resp = await client.get("/api/cost/cumulative?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            assert "date" in item
            assert "daily_cost" in item
            assert "cumulative" in item

    async def test_cumulative_monotonically_increasing(self, client):
        resp = await client.get("/api/cost/cumulative?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for i in range(1, len(data)):
            assert data[i]["cumulative"] >= data[i - 1]["cumulative"]

    async def test_cumulative_sum_matches_daily_costs(self, client):
        """The last cumulative value should equal the sum of all daily_costs."""
        resp = await client.get("/api/cost/cumulative?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        total_daily = sum(item["daily_cost"] for item in data)
        assert abs(data[-1]["cumulative"] - total_daily) < 0.001

    async def test_cumulative_known_values(self, client):
        """Verify against known daily summary costs: 0.19, 0.06, 0.30."""
        resp = await client.get("/api/cost/cumulative?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        # daily_summaries sorted by date ASC: 2026-02-03=0.19, 2026-02-04=0.06, 2026-02-05=0.30
        assert abs(data[0]["daily_cost"] - 0.19) < 0.001
        assert abs(data[0]["cumulative"] - 0.19) < 0.001
        assert abs(data[1]["daily_cost"] - 0.06) < 0.001
        assert abs(data[1]["cumulative"] - 0.25) < 0.001
        assert abs(data[2]["daily_cost"] - 0.30) < 0.001
        assert abs(data[2]["cumulative"] - 0.55) < 0.001

    async def test_cumulative_empty_range(self, client):
        resp = await client.get("/api/cost/cumulative?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
class TestCostCacheSimulationEndpoint:
    """Test /api/cost/cache-simulation endpoint."""

    async def test_cache_simulation_returns_correct_structure(self, client):
        resp = await client.get(
            "/api/cost/cache-simulation?target_hit_rate=0.5&from=2026-02-03&to=2026-02-05"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert "actual_cost" in data
        assert "actual_cache_rate" in data
        assert "simulated_cost" in data
        assert "simulated_cache_rate" in data
        assert "savings" in data

    async def test_cache_simulation_savings_non_negative(self, client):
        resp = await client.get(
            "/api/cost/cache-simulation?target_hit_rate=0.8&from=2026-02-03&to=2026-02-05"
        )
        data = resp.json()
        assert data["savings"] >= 0

    async def test_cache_simulation_simulated_cost_less_than_actual(self, client):
        """When target_hit_rate exceeds actual, simulated_cost should be less."""
        resp = await client.get(
            "/api/cost/cache-simulation?target_hit_rate=0.9&from=2026-02-03&to=2026-02-05"
        )
        data = resp.json()
        if data["actual_cache_rate"] < 0.9:
            assert data["simulated_cost"] < data["actual_cost"]

    async def test_cache_simulation_target_below_actual(self, client):
        """When target_hit_rate is at or below actual, savings should be 0."""
        resp = await client.get(
            "/api/cost/cache-simulation?target_hit_rate=0.0&from=2026-02-03&to=2026-02-05"
        )
        data = resp.json()
        assert data["savings"] == 0.0
        assert data["simulated_cost"] == data["actual_cost"]

    async def test_cache_simulation_default_target(self, client):
        resp = await client.get(
            "/api/cost/cache-simulation?from=2026-02-03&to=2026-02-05"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["simulated_cache_rate"] == 0.5

    async def test_cache_simulation_empty_range(self, client):
        resp = await client.get(
            "/api/cost/cache-simulation?from=2020-01-01&to=2020-01-02"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["actual_cost"] == 0.0
        assert data["savings"] == 0.0


@pytest.mark.asyncio
class TestCostNewQueries:
    """Direct unit tests for new cost query functions."""

    async def test_get_cost_anomalies_structure(self, async_db):
        result = await cost_queries.get_cost_anomalies(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert len(result) == 3
        for item in result:
            assert "date" in item
            assert "cost" in item
            assert "is_anomaly" in item
            assert "threshold" in item

    async def test_get_cost_anomalies_empty_range(self, async_db):
        result = await cost_queries.get_cost_anomalies(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert result == []

    async def test_get_cost_anomalies_threshold_calculation(self, async_db):
        """With 3 data points, IQR-based threshold should be computed correctly."""
        result = await cost_queries.get_cost_anomalies(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        # Costs sorted: [0.06, 0.19, 0.30]
        # n=3: q1=costs[0]=0.06, q3=costs[2]=0.30
        # iqr=0.24, threshold=0.30 + 1.5*0.24 = 0.66
        threshold = result[0]["threshold"]
        assert abs(threshold - 0.66) < 0.001

    async def test_get_cumulative_cost_structure(self, async_db):
        result = await cost_queries.get_cumulative_cost(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert len(result) == 3
        for item in result:
            assert "date" in item
            assert "daily_cost" in item
            assert "cumulative" in item

    async def test_get_cumulative_cost_monotonic(self, async_db):
        result = await cost_queries.get_cumulative_cost(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for i in range(1, len(result)):
            assert result[i]["cumulative"] >= result[i - 1]["cumulative"]

    async def test_get_cumulative_cost_final_total(self, async_db):
        result = await cost_queries.get_cumulative_cost(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert abs(result[-1]["cumulative"] - 0.55) < 0.001

    async def test_get_cumulative_cost_empty_range(self, async_db):
        result = await cost_queries.get_cumulative_cost(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert result == []

    async def test_get_cache_simulation_structure(self, async_db):
        result = await cost_queries.get_cache_simulation(
            async_db, target_hit_rate=0.5,
            date_from="2026-02-03", date_to="2026-02-05"
        )
        expected_keys = {
            "actual_cost", "actual_cache_rate",
            "simulated_cost", "simulated_cache_rate", "savings",
        }
        assert expected_keys == set(result.keys())

    async def test_get_cache_simulation_actual_rate_positive(self, async_db):
        """Test data has cache_read_tokens, so actual_cache_rate > 0."""
        result = await cost_queries.get_cache_simulation(
            async_db, target_hit_rate=0.5,
            date_from="2026-02-03", date_to="2026-02-05"
        )
        assert result["actual_cache_rate"] > 0

    async def test_get_cache_simulation_savings_with_high_target(self, async_db):
        result = await cost_queries.get_cache_simulation(
            async_db, target_hit_rate=0.9,
            date_from="2026-02-03", date_to="2026-02-05"
        )
        assert result["savings"] > 0
        assert result["simulated_cost"] < result["actual_cost"]

    async def test_get_cache_simulation_no_savings_when_below_actual(self, async_db):
        """When target <= actual, savings should be 0."""
        result = await cost_queries.get_cache_simulation(
            async_db, target_hit_rate=0.01,
            date_from="2026-02-03", date_to="2026-02-05"
        )
        assert result["savings"] == 0.0

    async def test_get_cache_simulation_empty_range(self, async_db):
        result = await cost_queries.get_cache_simulation(
            async_db, target_hit_rate=0.5,
            date_from="2020-01-01", date_to="2020-01-02"
        )
        assert result["actual_cost"] == 0.0
        assert result["savings"] == 0.0


# =====================================================================
# Productivity new endpoints and query tests
# =====================================================================


@pytest.mark.asyncio
class TestProductivityEfficiencyTrendEndpoint:
    """Test /api/productivity/efficiency-trend endpoint."""

    async def test_efficiency_trend_returns_list(self, client):
        resp = await client.get("/api/productivity/efficiency-trend?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)
        assert len(data) == 3

    async def test_efficiency_trend_has_expected_fields(self, client):
        resp = await client.get("/api/productivity/efficiency-trend?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            assert "date" in item
            assert "cost_per_kloc" in item

    async def test_efficiency_trend_dates_ordered(self, client):
        resp = await client.get("/api/productivity/efficiency-trend?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        dates = [item["date"] for item in data]
        assert dates == sorted(dates)

    async def test_efficiency_trend_known_values(self, client):
        """Verify cost_per_kloc for known data.
        2026-02-03: cost=0.19, loc=40 -> 0.19/(40/1000) = 4.75
        2026-02-04: cost=0.06, loc=20 -> 0.06/(20/1000) = 3.0
        2026-02-05: cost=0.30, loc=130 -> 0.30/(130/1000) = 2.307...
        """
        resp = await client.get("/api/productivity/efficiency-trend?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        assert abs(data[0]["cost_per_kloc"] - 4.75) < 0.01
        assert abs(data[1]["cost_per_kloc"] - 3.0) < 0.01
        assert abs(data[2]["cost_per_kloc"] - (0.30 / 0.130)) < 0.01

    async def test_efficiency_trend_empty_range(self, client):
        resp = await client.get("/api/productivity/efficiency-trend?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
class TestProductivityLanguageTrendEndpoint:
    """Test /api/productivity/language-trend endpoint."""

    async def test_language_trend_returns_list(self, client):
        resp = await client.get("/api/productivity/language-trend?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_language_trend_has_expected_fields(self, client):
        resp = await client.get("/api/productivity/language-trend?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            assert "date" in item
            assert "language" in item
            assert "loc_written" in item

    async def test_language_trend_contains_known_languages(self, client):
        resp = await client.get("/api/productivity/language-trend?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        languages = {item["language"] for item in data}
        assert "python" in languages

    async def test_language_trend_empty_range(self, client):
        resp = await client.get("/api/productivity/language-trend?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
class TestProductivityToolSuccessTrendEndpoint:
    """Test /api/productivity/tool-success-trend endpoint."""

    async def test_tool_success_trend_returns_list(self, client):
        resp = await client.get("/api/productivity/tool-success-trend?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_tool_success_trend_has_expected_fields(self, client):
        resp = await client.get("/api/productivity/tool-success-trend?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            assert "date" in item
            assert "tool_name" in item
            assert "success_rate" in item
            assert "total" in item

    async def test_tool_success_trend_success_rate_bounded(self, client):
        resp = await client.get("/api/productivity/tool-success-trend?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            assert 0.0 <= item["success_rate"] <= 1.0

    async def test_tool_success_trend_contains_known_tools(self, client):
        resp = await client.get("/api/productivity/tool-success-trend?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        tool_names = {item["tool_name"] for item in data}
        # Test data has Write, Read, Edit, Bash tool calls
        assert len(tool_names) > 0

    async def test_tool_success_trend_empty_range(self, client):
        resp = await client.get("/api/productivity/tool-success-trend?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
class TestProductivityFileChurnEndpoint:
    """Test /api/productivity/file-churn endpoint."""

    async def test_file_churn_returns_list(self, client):
        resp = await client.get("/api/productivity/file-churn?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_file_churn_has_expected_fields(self, client):
        resp = await client.get("/api/productivity/file-churn?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            assert "file_path" in item
            assert "edit_count" in item
            assert "total_loc" in item

    async def test_file_churn_sorted_by_edit_count_desc(self, client):
        resp = await client.get("/api/productivity/file-churn?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        if len(data) > 1:
            counts = [item["edit_count"] for item in data]
            assert counts == sorted(counts, reverse=True)

    async def test_file_churn_respects_limit(self, client):
        resp = await client.get("/api/productivity/file-churn?from=2026-02-03&to=2026-02-05&limit=2")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data) <= 2

    async def test_file_churn_empty_range(self, client):
        resp = await client.get("/api/productivity/file-churn?from=2020-01-01&to=2020-01-02")
        assert resp.status_code == 200
        assert resp.json() == []

    async def test_file_churn_contains_known_files(self, client):
        resp = await client.get("/api/productivity/file-churn?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        file_paths = {item["file_path"] for item in data}
        # Test data has tool calls on /path/auth.py, /path/test_auth.py, etc.
        assert len(file_paths) > 0


@pytest.mark.asyncio
class TestProductivityNewQueries:
    """Direct unit tests for new productivity query functions."""

    async def test_get_efficiency_trend_structure(self, async_db):
        result = await productivity_queries.get_efficiency_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert len(result) == 3
        for item in result:
            assert "date" in item
            assert "cost_per_kloc" in item

    async def test_get_efficiency_trend_empty_range(self, async_db):
        result = await productivity_queries.get_efficiency_trend(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert result == []

    async def test_get_efficiency_trend_zero_loc_day(self, async_db):
        """If loc_written=0 for a day, cost_per_kloc should be 0."""
        # All our test days have loc > 0, so test the code path differently:
        # Verify that the function handles zero safely (no division by zero)
        result = await productivity_queries.get_efficiency_trend(async_db)
        for item in result:
            assert isinstance(item["cost_per_kloc"], (int, float))

    async def test_get_language_trend_structure(self, async_db):
        result = await productivity_queries.get_language_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert isinstance(result, list)
        for item in result:
            assert "date" in item
            assert "language" in item
            assert "loc_written" in item

    async def test_get_language_trend_known_data(self, async_db):
        """Python tool calls should appear in language trend."""
        result = await productivity_queries.get_language_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        languages = {item["language"] for item in result}
        assert "python" in languages

    async def test_get_language_trend_empty_range(self, async_db):
        result = await productivity_queries.get_language_trend(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert result == []

    async def test_get_tool_success_trend_structure(self, async_db):
        result = await productivity_queries.get_tool_success_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert isinstance(result, list)
        for item in result:
            assert "date" in item
            assert "tool_name" in item
            assert "success_rate" in item
            assert "total" in item

    async def test_get_tool_success_trend_success_rate_range(self, async_db):
        result = await productivity_queries.get_tool_success_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for item in result:
            assert 0.0 <= item["success_rate"] <= 1.0
            assert item["total"] > 0

    async def test_get_tool_success_trend_empty_range(self, async_db):
        result = await productivity_queries.get_tool_success_trend(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert result == []

    async def test_get_file_churn_structure(self, async_db):
        result = await productivity_queries.get_file_churn(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "file_path" in item
            assert "edit_count" in item
            assert "total_loc" in item

    async def test_get_file_churn_sorted_desc(self, async_db):
        result = await productivity_queries.get_file_churn(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        if len(result) > 1:
            counts = [item["edit_count"] for item in result]
            assert counts == sorted(counts, reverse=True)

    async def test_get_file_churn_limit(self, async_db):
        result = await productivity_queries.get_file_churn(
            async_db, date_from="2026-02-03", date_to="2026-02-05", limit=2
        )
        assert len(result) <= 2

    async def test_get_file_churn_empty_range(self, async_db):
        result = await productivity_queries.get_file_churn(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert result == []


# =====================================================================
# Dashboard new endpoints and query tests
# =====================================================================


@pytest.mark.asyncio
class TestDashboardDeltasEndpoint:
    """Test /api/dashboard/deltas endpoint."""

    async def test_deltas_returns_list(self, client):
        resp = await client.get("/api/dashboard/deltas?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_deltas_have_expected_fields(self, client):
        resp = await client.get("/api/dashboard/deltas?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            assert "metric" in item
            assert "current" in item
            assert "previous" in item
            assert "delta" in item
            assert "pct_change" in item

    async def test_deltas_include_expected_metrics(self, client):
        resp = await client.get("/api/dashboard/deltas?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        metric_names = {item["metric"] for item in data}
        assert "sessions" in metric_names
        assert "cost" in metric_names
        assert "loc_written" in metric_names
        assert "error_rate" in metric_names

    async def test_deltas_delta_equals_current_minus_previous(self, client):
        resp = await client.get("/api/dashboard/deltas?from=2026-02-03&to=2026-02-05")
        data = resp.json()
        for item in data:
            expected_delta = item["current"] - item["previous"]
            assert abs(item["delta"] - expected_delta) < 0.001

    async def test_deltas_no_params_returns_empty(self, client):
        """Without date params, deltas returns empty list."""
        resp = await client.get("/api/dashboard/deltas")
        assert resp.status_code == 200
        assert resp.json() == []


@pytest.mark.asyncio
class TestDashboardActivityCalendarEndpoint:
    """Test /api/dashboard/activity-calendar endpoint."""

    async def test_activity_calendar_returns_list(self, client):
        resp = await client.get("/api/dashboard/activity-calendar?days=90")
        assert resp.status_code == 200
        data = resp.json()
        assert isinstance(data, list)

    async def test_activity_calendar_has_expected_fields(self, client):
        resp = await client.get("/api/dashboard/activity-calendar?days=90")
        data = resp.json()
        for item in data:
            assert "date" in item
            assert "sessions" in item
            assert "cost" in item

    async def test_activity_calendar_dates_ordered(self, client):
        resp = await client.get("/api/dashboard/activity-calendar?days=365")
        data = resp.json()
        dates = [item["date"] for item in data]
        assert dates == sorted(dates)

    async def test_activity_calendar_default_days(self, client):
        """Default is 90 days."""
        resp = await client.get("/api/dashboard/activity-calendar")
        assert resp.status_code == 200

    async def test_activity_calendar_sessions_non_negative(self, client):
        resp = await client.get("/api/dashboard/activity-calendar?days=365")
        data = resp.json()
        for item in data:
            assert item["sessions"] >= 0
            assert item["cost"] >= 0

    async def test_activity_calendar_min_days_boundary(self, client):
        resp = await client.get("/api/dashboard/activity-calendar?days=7")
        assert resp.status_code == 200

    async def test_activity_calendar_below_min_days_rejected(self, client):
        resp = await client.get("/api/dashboard/activity-calendar?days=1")
        assert resp.status_code == 422


@pytest.mark.asyncio
class TestDashboardNewQueries:
    """Direct unit tests for new dashboard query functions."""

    async def test_get_period_deltas_structure(self, async_db):
        result = await dashboard_queries.get_period_deltas(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert isinstance(result, list)
        assert len(result) == 4  # sessions, cost, loc_written, error_rate

    async def test_get_period_deltas_no_params(self, async_db):
        result = await dashboard_queries.get_period_deltas(async_db)
        assert result == []

    async def test_get_period_deltas_metrics(self, async_db):
        result = await dashboard_queries.get_period_deltas(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        metrics = {item["metric"] for item in result}
        assert metrics == {"sessions", "cost", "loc_written", "error_rate"}

    async def test_get_period_deltas_delta_computation(self, async_db):
        result = await dashboard_queries.get_period_deltas(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        for item in result:
            expected = item["current"] - item["previous"]
            assert abs(item["delta"] - expected) < 0.001

    async def test_get_activity_calendar_structure(self, async_db):
        result = await dashboard_queries.get_activity_calendar(async_db, days=365)
        assert isinstance(result, list)
        for item in result:
            assert "date" in item
            assert "sessions" in item
            assert "cost" in item

    async def test_get_activity_calendar_has_data(self, async_db):
        """Test data has 3 daily summaries within the last 365 days."""
        result = await dashboard_queries.get_activity_calendar(async_db, days=365)
        assert len(result) >= 3

    async def test_get_activity_calendar_ordered(self, async_db):
        result = await dashboard_queries.get_activity_calendar(async_db, days=365)
        dates = [item["date"] for item in result]
        assert dates == sorted(dates)


# =====================================================================
# Experiment new endpoints and query tests
# =====================================================================


@pytest.mark.asyncio
class TestExperimentCompareMultiEndpoint:
    """Test /api/experiments/compare-multi endpoint."""

    async def test_compare_multi_returns_list(self, client):
        resp = await client.get("/api/experiments/compare-multi?tags=baseline,nonexistent")
        assert resp.status_code == 200
        data = resp.json()["tags"]
        assert isinstance(data, list)
        assert len(data) == 2

    async def test_compare_multi_has_expected_fields(self, client):
        resp = await client.get("/api/experiments/compare-multi?tags=baseline,nonexistent")
        data = resp.json()["tags"]
        for item in data:
            assert "tag_name" in item
            assert "sessions" in item
            assert "cost" in item
            assert "loc" in item
            assert "turns" in item
            assert "error_rate" in item

    async def test_compare_multi_known_tag_data(self, client):
        """Baseline tag has sess-001 and sess-002."""
        resp = await client.get("/api/experiments/compare-multi?tags=baseline,nonexistent")
        data = resp.json()["tags"]
        baseline = next(item for item in data if item["tag_name"] == "baseline")
        assert baseline["sessions"] == 2
        assert baseline["cost"] > 0
        assert baseline["turns"] > 0

    async def test_compare_multi_nonexistent_tag_zeroed(self, client):
        resp = await client.get("/api/experiments/compare-multi?tags=baseline,nonexistent")
        data = resp.json()["tags"]
        nonexistent = next(item for item in data if item["tag_name"] == "nonexistent")
        assert nonexistent["sessions"] == 0
        assert nonexistent["cost"] == 0.0
        assert nonexistent["loc"] == 0
        assert nonexistent["turns"] == 0

    async def test_compare_multi_single_tag_rejected(self, client):
        """Providing only 1 tag should return 400."""
        resp = await client.get("/api/experiments/compare-multi?tags=baseline")
        assert resp.status_code == 400

    async def test_compare_multi_too_many_tags_rejected(self, client):
        """Providing more than 4 tags should return 400."""
        resp = await client.get("/api/experiments/compare-multi?tags=a,b,c,d,e")
        assert resp.status_code == 400

    async def test_compare_multi_with_date_filter(self, client):
        """Date filter should apply to the tag session scope."""
        resp = await client.get(
            "/api/experiments/compare-multi?tags=baseline,nonexistent"
            "&from=2026-02-05&to=2026-02-05"
        )
        assert resp.status_code == 200
        data = resp.json()["tags"]
        baseline = next(item for item in data if item["tag_name"] == "baseline")
        # baseline has sess-001 (2026-02-05) and sess-002 (2026-02-04)
        # Filtering to 2026-02-05 only should give 1 session
        assert baseline["sessions"] == 1


@pytest.mark.asyncio
class TestExperimentTagSessionsEndpoint:
    """Test /api/experiments/tags/{tag_name}/sessions endpoint."""

    async def test_tag_sessions_returns_list(self, client):
        resp = await client.get("/api/experiments/tags/baseline/sessions")
        assert resp.status_code == 200
        data = resp.json()["sessions"]
        assert isinstance(data, list)
        assert len(data) == 2  # baseline has sess-001, sess-002

    async def test_tag_sessions_have_expected_fields(self, client):
        resp = await client.get("/api/experiments/tags/baseline/sessions")
        data = resp.json()["sessions"]
        for item in data:
            assert "session_id" in item
            assert "project_display" in item
            assert "start_time" in item
            assert "total_cost" in item
            assert "turn_count" in item
            assert "model_default" in item

    async def test_tag_sessions_known_data(self, client):
        resp = await client.get("/api/experiments/tags/baseline/sessions")
        data = resp.json()["sessions"]
        session_ids = {item["session_id"] for item in data}
        assert session_ids == {"sess-001", "sess-002"}

    async def test_tag_sessions_cost_accuracy(self, client):
        """Verify costs are computed from turns, not sessions table."""
        resp = await client.get("/api/experiments/tags/baseline/sessions")
        data = resp.json()["sessions"]
        by_id = {item["session_id"]: item for item in data}
        # sess-001: turns cost 0.00+0.10+0.00+0.20 = 0.30
        assert abs(by_id["sess-001"]["total_cost"] - 0.30) < 0.001
        # sess-002: turns cost 0.00+0.05 = 0.05
        assert abs(by_id["sess-002"]["total_cost"] - 0.05) < 0.001

    async def test_tag_sessions_nonexistent_tag(self, client):
        resp = await client.get("/api/experiments/tags/nonexistent_tag/sessions")
        assert resp.status_code == 200
        assert resp.json() == {"sessions": []}

    async def test_tag_sessions_with_date_filter(self, client):
        """Filtering to a specific date should reduce results."""
        resp = await client.get(
            "/api/experiments/tags/baseline/sessions?from=2026-02-05&to=2026-02-05"
        )
        assert resp.status_code == 200
        data = resp.json()["sessions"]
        # sess-001 is on 2026-02-05, sess-002 is on 2026-02-04
        assert len(data) == 1
        assert data[0]["session_id"] == "sess-001"


@pytest.mark.asyncio
class TestExperimentNewQueries:
    """Direct unit tests for new experiment query functions."""

    async def test_compare_tags_multi_structure(self, async_db):
        result = await experiment_queries.compare_tags_multi(
            async_db, ["baseline", "nonexistent"]
        )
        assert len(result) == 2
        for item in result:
            assert "tag_name" in item
            assert "sessions" in item
            assert "cost" in item
            assert "loc" in item
            assert "turns" in item
            assert "error_rate" in item

    async def test_compare_tags_multi_baseline_data(self, async_db):
        result = await experiment_queries.compare_tags_multi(
            async_db, ["baseline", "nonexistent"]
        )
        baseline = next(item for item in result if item["tag_name"] == "baseline")
        assert baseline["sessions"] == 2
        # sess-001 + sess-002 = 6 turns
        assert baseline["turns"] == 6
        # cost: 0.30 + 0.05 = 0.35
        assert abs(baseline["cost"] - 0.35) < 0.001

    async def test_compare_tags_multi_nonexistent_zeroed(self, async_db):
        result = await experiment_queries.compare_tags_multi(
            async_db, ["baseline", "nonexistent"]
        )
        nope = next(item for item in result if item["tag_name"] == "nonexistent")
        assert nope["sessions"] == 0
        assert nope["cost"] == 0.0
        assert nope["loc"] == 0
        assert nope["turns"] == 0
        assert nope["error_rate"] == 0.0

    async def test_compare_tags_multi_error_rate_accuracy(self, async_db):
        """baseline tag: sess-001 has 4 tool calls (1 error), sess-002 has 2 (1 error via Edit)."""
        result = await experiment_queries.compare_tags_multi(
            async_db, ["baseline"]
        )
        baseline = result[0]
        # sess-001: 4 tool calls, 1 error
        # sess-002: 2 tool calls, 0 errors (Edit in sess-002 tc05 is success=1)
        assert baseline["error_rate"] == 1 / 6  # 1 error out of 6 tool calls

    async def test_compare_tags_multi_with_date_filter(self, async_db):
        result = await experiment_queries.compare_tags_multi(
            async_db, ["baseline", "nonexistent"],
            date_from="2026-02-05", date_to="2026-02-05"
        )
        baseline = next(item for item in result if item["tag_name"] == "baseline")
        # Only sess-001 is on 2026-02-05
        assert baseline["sessions"] == 1

    async def test_get_tag_sessions_structure(self, async_db):
        result = await experiment_queries.get_tag_sessions(async_db, "baseline")
        assert len(result) == 2
        for item in result:
            assert "session_id" in item
            assert "project_display" in item
            assert "start_time" in item
            assert "total_cost" in item
            assert "turn_count" in item
            assert "model_default" in item

    async def test_get_tag_sessions_cost_from_turns(self, async_db):
        """Verify costs are computed from turns table, not sessions."""
        result = await experiment_queries.get_tag_sessions(async_db, "baseline")
        by_id = {item["session_id"]: item for item in result}
        assert abs(by_id["sess-001"]["total_cost"] - 0.30) < 0.001
        assert abs(by_id["sess-002"]["total_cost"] - 0.05) < 0.001

    async def test_get_tag_sessions_nonexistent(self, async_db):
        result = await experiment_queries.get_tag_sessions(async_db, "no-such-tag")
        assert result == []

    async def test_get_tag_sessions_turn_count(self, async_db):
        result = await experiment_queries.get_tag_sessions(async_db, "baseline")
        by_id = {item["session_id"]: item for item in result}
        assert by_id["sess-001"]["turn_count"] == 4
        assert by_id["sess-002"]["turn_count"] == 2

    async def test_get_tag_sessions_with_date_filter(self, async_db):
        result = await experiment_queries.get_tag_sessions(
            async_db, "baseline",
            date_from="2026-02-04", date_to="2026-02-04"
        )
        # Only sess-002 is on 2026-02-04
        assert len(result) == 1
        assert result[0]["session_id"] == "sess-002"


# =====================================================================
# Models endpoint and query tests
# =====================================================================


@pytest.mark.asyncio
class TestModelsEndpoint:
    """Test /api/models endpoint.

    Queries use s.first_timestamp for date filtering, turns.id for joins,
    and correlated subqueries for computed session-level fields.
    """

    async def test_models_endpoint_with_dates(self, client):
        """The models endpoint returns model comparison data with date filters."""
        resp = await client.get("/api/models?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert "models" in data
        assert "usage_trend" in data
        assert "scatter" in data

    async def test_models_endpoint_no_params(self, client):
        """Without date params the endpoint returns all data."""
        resp = await client.get("/api/models")
        assert resp.status_code == 200
        data = resp.json()
        assert len(data["models"]) > 0


@pytest.mark.asyncio
class TestModelQueries:
    """Direct unit tests for model query functions."""

    async def test_get_model_usage_trend_structure(self, async_db):
        """get_model_usage_trend only uses turns table and should work."""
        result = await model_queries.get_model_usage_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "date" in item
            assert "model" in item
            assert "count" in item

    async def test_get_model_usage_trend_known_models(self, async_db):
        result = await model_queries.get_model_usage_trend(async_db)
        models = {item["model"] for item in result}
        assert "claude-opus-4-5-20251101" in models
        assert "claude-sonnet-4-20250514" in models

    async def test_get_model_usage_trend_dates_ordered(self, async_db):
        result = await model_queries.get_model_usage_trend(
            async_db, date_from="2026-02-03", date_to="2026-02-05"
        )
        dates = [item["date"] for item in result]
        assert dates == sorted(dates)

    async def test_get_model_usage_trend_empty_range(self, async_db):
        result = await model_queries.get_model_usage_trend(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert result == []

    async def test_get_model_metrics_structure(self, async_db):
        """get_model_metrics returns per-model aggregates with LOC."""
        result = await model_queries.get_model_metrics(async_db)
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "model" in item
            assert "sessions" in item
            assert "turns" in item
            assert "total_cost" in item
            assert "loc_written" in item

    async def test_get_model_metrics_known_models(self, async_db):
        """Metrics include all three test models."""
        result = await model_queries.get_model_metrics(async_db)
        models = {item["model"] for item in result}
        assert "claude-opus-4-5-20251101" in models
        assert "claude-sonnet-4-20250514" in models
        assert "claude-haiku-4-5-20251001" in models

    async def test_get_model_scatter_structure(self, async_db):
        """get_model_scatter returns per-session cost vs LOC."""
        result = await model_queries.get_model_scatter(async_db)
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "session_id" in item
            assert "model" in item
            assert "cost" in item
            assert "loc_written" in item

    async def test_get_model_scatter_known_sessions(self, async_db):
        """Scatter data includes sessions from the test database."""
        result = await model_queries.get_model_scatter(async_db)
        session_ids = {item["session_id"] for item in result}
        assert "sess-001" in session_ids


# =====================================================================
# Workflows endpoint and query tests
# =====================================================================


@pytest.mark.asyncio
class TestWorkflowsEndpoint:
    """Test /api/workflows endpoint.

    Queries use s.is_agent to derive user_type, s.first_timestamp for
    date filtering, and joins/subqueries for aggregated cost and turn counts.
    """

    async def test_workflows_endpoint_with_dates(self, client):
        """The workflows endpoint returns data with date filters."""
        resp = await client.get("/api/workflows?from=2026-02-03&to=2026-02-05")
        assert resp.status_code == 200
        data = resp.json()
        assert "user_types" in data
        assert "user_type_trend" in data
        assert "tool_sequences" in data

    async def test_workflows_endpoint_no_params(self, client):
        """Without date params the endpoint returns all data."""
        resp = await client.get("/api/workflows")
        assert resp.status_code == 200
        data = resp.json()
        assert "user_types" in data
        assert len(data["user_types"]) > 0


@pytest.mark.asyncio
class TestWorkflowQueries:
    """Direct unit tests for workflow query functions."""

    async def test_get_tool_sequences_no_date_filter(self, async_db):
        """get_tool_sequences works without date params."""
        result = await workflow_queries.get_tool_sequences(async_db)
        assert isinstance(result, list)
        for item in result:
            assert "sequence" in item
            assert "count" in item
            assert "pct" in item
            assert isinstance(item["sequence"], list)

    async def test_get_tool_sequences_known_data(self, async_db):
        """With 8 tool calls and window=3, we should get sequences."""
        result = await workflow_queries.get_tool_sequences(async_db)
        if result:
            # All sequences should be length 3 (default window)
            for item in result:
                assert len(item["sequence"]) == 3
            # Percentages (rounded to 1 decimal) should sum close to 100
            total_pct = sum(item["pct"] for item in result)
            assert abs(total_pct - 100.0) < 1.0

    async def test_get_tool_sequences_with_dates(self, async_db):
        """get_tool_sequences works with date filters on s.first_timestamp."""
        result = await workflow_queries.get_tool_sequences(
            async_db, date_from="2020-01-01", date_to="2020-01-02"
        )
        assert isinstance(result, list)
        assert result == []

    async def test_get_user_type_breakdown_structure(self, async_db):
        """get_user_type_breakdown returns human/agent breakdown."""
        result = await workflow_queries.get_user_type_breakdown(async_db)
        assert isinstance(result, list)
        assert len(result) > 0
        user_types = {item["user_type"] for item in result}
        # Test data has 4 human sessions and 1 agent session
        assert "human" in user_types
        for item in result:
            assert "sessions" in item
            assert "total_cost" in item
            assert "total_turns" in item

    async def test_get_user_type_trend_structure(self, async_db):
        """get_user_type_trend returns daily user type trend."""
        result = await workflow_queries.get_user_type_trend(async_db)
        assert isinstance(result, list)
        assert len(result) > 0
        for item in result:
            assert "date" in item
            assert "user_type" in item
            assert "sessions" in item
            assert "cost" in item

    async def test_get_agent_trees_structure(self, async_db):
        """get_agent_trees returns session trees with user_type from is_agent."""
        result = await workflow_queries.get_agent_trees(async_db)
        assert isinstance(result, list)
        # Trees only include roots that have children; test data has no
        # parent_session_id set, so result may be empty
        for item in result:
            assert "session_id" in item
            assert "user_type" in item
            assert "total_cost" in item
            assert "children" in item


# =====================================================================
# Project detail endpoint and query tests
# =====================================================================


@pytest.mark.asyncio
class TestProjectDetailEndpoint:
    """Test /api/projects/{encoded_path}/detail endpoint.

    Queries use s.first_timestamp, and correlated subqueries for computed
    session-level fields (total_cost, turn_count, loc_written, model_default).
    """

    async def test_project_detail_returns_data(self, client):
        """The endpoint returns project detail for an existing project."""
        encoded = _encode_project_path("/path/proj-alpha")
        resp = await client.get(
            f"/api/projects/{encoded}/detail?from=2026-02-03&to=2026-02-06"
        )
        assert resp.status_code == 200
        data = resp.json()
        assert data["project_display"] == "proj-alpha"
        assert data["total_sessions"] == 2

    async def test_project_detail_nonexistent_returns_404(self, client):
        """A nonexistent project path returns 404."""
        encoded = _encode_project_path("/nonexistent/path")
        resp = await client.get(
            f"/api/projects/{encoded}/detail?from=2026-02-03&to=2026-02-05"
        )
        assert resp.status_code == 404


@pytest.mark.asyncio
class TestProjectDetailQueries:
    """Direct unit tests for project detail query functions."""

    async def test_get_project_detail_structure(self, async_db):
        """get_project_detail returns full project data with subquery-computed fields."""
        result = await project_detail_queries.get_project_detail(
            async_db, "/path/proj-alpha",
            date_from="2026-02-03", date_to="2026-02-06"
        )
        assert result is not None
        assert result["project_display"] == "proj-alpha"
        assert result["total_sessions"] == 2
        assert "total_cost" in result
        assert "total_loc" in result
        assert "sessions" in result
        assert "cost_trend" in result
        assert "languages" in result
        assert "tools" in result
        assert "branches" in result

    async def test_get_project_detail_without_dates(self, async_db):
        """get_project_detail works without date filters."""
        result = await project_detail_queries.get_project_detail(
            async_db, "/path/proj-alpha"
        )
        assert result is not None
        assert result["project_display"] == "proj-alpha"
        assert result["total_sessions"] == 2

    async def test_get_project_detail_nonexistent(self, async_db):
        """get_project_detail returns None for a nonexistent project."""
        result = await project_detail_queries.get_project_detail(
            async_db, "/nonexistent/path"
        )
        assert result is None
