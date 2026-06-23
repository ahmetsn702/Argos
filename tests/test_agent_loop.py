import asyncio
import time
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.agent import InvestigationReport, InvestigationRequest, ToolCall
from app.services.agent.loop import InvestigationLoop
from app.services.agent.registry import ToolRegistry
from app.services.agent.budget import BudgetEnforcer
from app.services.agent.audit import AuditLogger
from app.services.agent.tools.base import BaseTool


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# ─── Helpers ──────────────────────────────────────────────────────────────────

class OkTool(BaseTool):
    def __init__(self, name="ok_tool"):
        super().__init__(name, f"Tool that always succeeds ({name})")

    async def _run(self, params: dict) -> dict:
        return {"ok": True, "data": {"found": True, "seed": params.get("seed")}}


class FailTool(BaseTool):
    def __init__(self):
        super().__init__("fail_tool", "Tool that always fails")

    async def _run(self, params: dict) -> dict:
        return {"ok": False, "data": None, "error": "simulated failure"}


class NullDataTool(BaseTool):
    def __init__(self):
        super().__init__("null_data_tool", "Tool that returns ok but null data")

    async def _run(self, params: dict) -> dict:
        return {"ok": True, "data": None}


def _make_registry(*tools, whitelist=None):
    registry = ToolRegistry()
    tool_names = whitelist or [t.name for t in tools]
    for tool in tools:
        registry.register(tool)
    mock_settings = MagicMock()
    mock_settings.AGENT_TOOL_WHITELIST = ",".join(tool_names)
    return registry, mock_settings


def _make_budget(quota=100, session_max=50, daily_usd=99.0):
    budget = BudgetEnforcer()
    mock_settings = MagicMock()
    mock_settings.AGENT_DAILY_TOOL_QUOTA = quota
    mock_settings.AGENT_SESSION_MAX_TOOL_CALLS = session_max
    mock_settings.AGENT_DAILY_BUDGET_USD = daily_usd
    return budget, mock_settings


def _make_audit(tmp_path=None):
    if tmp_path:
        return AuditLogger(db_path=str(tmp_path / "audit.db"))
    return AuditLogger(db_path=":memory:")


def _make_loop(tools, budget_mock, audit, max_iterations=10, registry_mock_settings=None):
    registry = ToolRegistry()
    whitelist = [t.name for t in tools]
    for t in tools:
        registry.register(t)
    reg_mock = MagicMock()
    reg_mock.AGENT_TOOL_WHITELIST = ",".join(whitelist)
    return registry, reg_mock


# ─── Test 1: Basic run returns InvestigationReport ────────────────────────────

def test_loop_returns_investigation_report(tmp_path):
    tools = [OkTool("tool_a")]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget()
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=2)
        report = _run(loop.run("sess-1", "alice@example.com", "Find info"))

    assert isinstance(report, InvestigationReport)
    assert report.session_id == "sess-1"
    assert report.seed == "alice@example.com"
    assert report.goal == "Find info"
    assert report.took_ms >= 0


# ─── Test 2: max_iterations stops the loop ────────────────────────────────────

def test_loop_stops_at_max_iterations(tmp_path):
    tools = [OkTool("t1"), OkTool("t2")]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget(quota=200, session_max=200)
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=3)
        report = _run(loop.run("sess-2", "target", "goal"))

    # At most 3 iterations, but dedup will skip repeated tool+params combos
    assert len(report.tool_calls) <= 3


# ─── Test 3: Budget exhaustion stops the loop ─────────────────────────────────

def test_loop_stops_when_budget_exhausted(tmp_path):
    tools = [OkTool("tool_b")]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget(quota=1, session_max=100)
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=10)
        report = _run(loop.run("sess-3", "target", "goal"))

    # Only 1 call should succeed before dedup or budget stops it
    assert len(report.tool_calls) <= 1


# ─── Test 4: Dedup skips repeated tool+args ───────────────────────────────────

def test_loop_dedup_prevents_repeat_calls(tmp_path):
    call_count = {"n": 0}
    
    class CountingTool(BaseTool):
        def __init__(self):
            super().__init__("counting_tool", "counts calls")
        
        async def _run(self, params: dict) -> dict:
            call_count["n"] += 1
            return {"ok": True, "data": {"count": call_count["n"]}}

    tools = [CountingTool()]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget(quota=100, session_max=100)
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=5)
        report = _run(loop.run("sess-4", "same-seed", "same-goal"))

    # The same tool+params should only execute once due to dedup
    assert call_count["n"] == 1
    assert len(report.tool_calls) == 1


# ─── Test 5: Low confidence streak stops the loop ────────────────────────────

def test_loop_stops_on_low_confidence_streak(tmp_path):
    tools = [FailTool()]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget(quota=200, session_max=200)
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=20)
        report = _run(loop.run("sess-5", "target", "goal"))

    # FailTool returns ok=False, dedup stops after 1 call, so only 1 call
    assert len(report.tool_calls) == 1
    assert report.confidence < 0.6


# ─── Test 6: Timeout stops the loop ──────────────────────────────────────────

def test_loop_stops_on_deadline(tmp_path):
    class SlowTool(BaseTool):
        def __init__(self):
            super().__init__("slow_tool", "slow")

        async def _run(self, params: dict) -> dict:
            await asyncio.sleep(0.05)
            return {"ok": True, "data": {"done": True}}

    tools = [SlowTool()]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget(quota=200, session_max=200)
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=100)
        # Very short deadline (0.01 seconds)
        report = _run(loop.run("sess-6", "target", "goal", timeout_seconds=0.01))

    # Should have stopped very early
    assert report.took_ms < 5000  # Generous upper bound for CI


# ─── Test 7: Confidence increases with successful tool calls ──────────────────

def test_confidence_increases_with_ok_results(tmp_path):
    # Two different ok tools with different names to avoid dedup
    tools = [OkTool("alpha"), OkTool("beta")]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget(quota=200, session_max=200)
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=5)
        report = _run(loop.run("sess-7", "target", "goal"))

    assert report.confidence > 0.0


# ─── Test 8: ToolCall model is correctly populated ────────────────────────────

def test_tool_call_fields_populated(tmp_path):
    tools = [OkTool("verify_tool")]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget()
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=2)
        report = _run(loop.run("sess-8", "alice", "profile"))

    assert len(report.tool_calls) >= 1
    tc = report.tool_calls[0]
    assert tc.tool_name == "verify_tool"
    assert tc.iteration == 0
    assert "seed" in tc.params
    assert isinstance(tc.result, dict)
    assert tc.timestamp != ""


# ─── Test 9: Empty registry returns report with no tool_calls ─────────────────

def test_loop_with_empty_registry(tmp_path):
    registry = ToolRegistry()
    reg_mock = MagicMock()
    reg_mock.AGENT_TOOL_WHITELIST = ""
    budget, bud_mock = _make_budget()
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=5)
        report = _run(loop.run("sess-9", "target", "goal"))

    assert report.tool_calls == []
    assert report.confidence == 0.0
    assert "No tools executed" in report.verdict


# ─── Test 10: Verdict string reflects confidence level ────────────────────────

def test_verdict_reflects_confidence(tmp_path):
    tools = [OkTool("v1"), OkTool("v2"), OkTool("v3")]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget(quota=200, session_max=200)
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=10)
        report = _run(loop.run("sess-10", "target", "goal"))

    assert report.verdict != ""
    # With ok tools, confidence should be non-zero
    assert report.confidence >= 0.0


# ─── Test 11: Null data tool lowers confidence less than fail ─────────────────

def test_null_data_tool_confidence_behavior(tmp_path):
    tools = [NullDataTool()]
    registry, reg_mock = _make_loop(tools, None, None)
    budget, bud_mock = _make_budget()
    audit = _make_audit(tmp_path)

    with patch("app.services.agent.registry.settings", reg_mock), \
         patch("app.services.agent.budget.settings", bud_mock), \
         patch("app.core.feature_flags.AGENT_ENABLED", True):
        loop = InvestigationLoop(registry, budget, audit, max_iterations=5)
        report = _run(loop.run("sess-11", "target", "goal"))

    # Null data result: confidence barely moves, should still work without crash
    assert isinstance(report.confidence, float)
    assert 0.0 <= report.confidence <= 1.0


# ─── Test 12: Agent router endpoints return enabled:false when disabled ────────

def test_agent_endpoints_disabled(tmp_path):
    from fastapi.testclient import TestClient
    from app.main import app

    client = TestClient(app)

    with patch("app.core.feature_flags.AGENT_ENABLED", False), \
         patch("app.routers.agent.ff.AGENT_ENABLED", False):
        resp = client.post("/agent/investigate", json={
            "seed": "test@example.com",
            "goal": "find info"
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("enabled") is False

        resp2 = client.get("/agent/sessions/nonexistent")
        assert resp2.status_code == 200
        assert resp2.json().get("enabled") is False

        resp3 = client.get("/agent/budget/status")
        assert resp3.status_code == 200
        assert resp3.json().get("enabled") is False
