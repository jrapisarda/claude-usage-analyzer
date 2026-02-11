"""Regression tests for advanced dashboards and saved views/alerts APIs."""

import pytest


@pytest.mark.asyncio
async def test_reliability_endpoint_returns_summary_and_breakdowns(client):
    resp = await client.get("/api/reliability?from=2026-02-03&to=2026-02-05")
    assert resp.status_code == 200

    data = resp.json()
    assert set(data.keys()) == {
        "summary",
        "heatmap",
        "pareto_tools",
        "pareto_commands",
        "pareto_languages",
        "by_branch",
        "top_failing_workflows",
    }
    assert data["summary"]["total_tool_calls"] >= 0
    assert data["summary"]["total_errors"] >= 0


@pytest.mark.asyncio
async def test_branch_health_endpoint_honors_branch_filter(client):
    resp = await client.get("/api/branch-health?from=2026-02-03&to=2026-02-05&branches=main")
    assert resp.status_code == 200

    data = resp.json()
    assert all(row["branch"] == "main" for row in data["branches"])
    assert all(row["branch"] == "main" for row in data["trend"])


@pytest.mark.asyncio
async def test_prompt_efficiency_endpoint_returns_scatter_and_outliers(client):
    resp = await client.get("/api/prompt-efficiency?from=2026-02-03&to=2026-02-05")
    assert resp.status_code == 200

    data = resp.json()
    assert data["summary"]["total_sessions"] > 0
    assert isinstance(data["scatter"], list)
    if data["scatter"]:
        first = data["scatter"][0]
        assert "session_id" in first
        assert "efficiency_score" in first


@pytest.mark.asyncio
async def test_workflow_bottlenecks_endpoint_returns_transition_matrix(client):
    resp = await client.get("/api/workflow-bottlenecks?from=2026-02-03&to=2026-02-05")
    assert resp.status_code == 200

    data = resp.json()
    assert "transition_matrix" in data
    assert "retry_loops" in data
    assert "blocked_sessions" in data
    assert len(data["transition_matrix"]) > 0


@pytest.mark.asyncio
async def test_saved_views_crud_flow(client):
    create = await client.post("/api/saved-views", json={
        "name": "Explorer by project",
        "page": "explorer",
        "filters": {
            "metric": "cost",
            "group_by": "project",
        },
    })
    assert create.status_code == 200
    created = create.json()
    view_id = created["id"]

    listed = await client.get("/api/saved-views?page=explorer")
    assert listed.status_code == 200
    ids = {row["id"] for row in listed.json()["views"]}
    assert view_id in ids

    deleted = await client.delete(f"/api/saved-views/{view_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1


@pytest.mark.asyncio
async def test_alert_rules_create_evaluate_and_delete(client):
    bad = await client.post("/api/alert-rules", json={
        "name": "Invalid operator",
        "page": "cost",
        "metric": "total_cost",
        "operator": "><",
        "threshold": 1.0,
        "filters": {},
        "enabled": True,
    })
    assert bad.status_code == 400

    create = await client.post("/api/alert-rules", json={
        "name": "Cost Watch",
        "page": "cost",
        "metric": "total_cost",
        "operator": ">",
        "threshold": 0.1,
        "filters": {},
        "enabled": True,
    })
    assert create.status_code == 200
    created = create.json()
    rule_id = created["id"]

    eval_resp = await client.get("/api/alert-rules/evaluate?page=cost&from=2026-02-03&to=2026-02-05")
    assert eval_resp.status_code == 200
    evaluations = eval_resp.json()["evaluations"]
    matched = next((row for row in evaluations if row["rule_id"] == rule_id), None)
    assert matched is not None
    assert matched["metric"] == "total_cost"
    assert matched["triggered"] is True

    deleted = await client.delete(f"/api/alert-rules/{rule_id}")
    assert deleted.status_code == 200
    assert deleted.json()["deleted"] == 1
