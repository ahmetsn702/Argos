import os
import pytest
import asyncio
from datetime import datetime, date, timezone
from unittest.mock import AsyncMock, MagicMock, patch

from app.services.agent.tools.base import BaseTool
from app.services.agent.tools import (
    EmailOsintTool, PhoneLookupTool, SocialScanTool,
    DomainLookupTool, ConfidenceBuildTool, TemporalAnalyzeTool,
    PivotRunTool, GraphQueryTool
)
from app.services.agent.registry import ToolRegistry
from app.services.agent.budget import BudgetEnforcer
from app.services.agent.audit import AuditLogger

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

def make_mock_client(mock_response):
    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=mock_response)
    mock_client.post = AsyncMock(return_value=mock_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock()
    return mock_client

class MockTool(BaseTool):
    def __init__(self):
        super().__init__("mock_tool", "Mock description")
        
    async def _run(self, params: dict) -> dict:
        if params.get("fail"):
            raise ValueError("Test failure")
        return {"ok": True, "data": params.get("value")}

# Test 1: Base Tool behavior (disabled, success, error cases)
def test_base_tool_behavior():
    tool = MockTool()
    # 1. Disabled case
    with patch("app.core.feature_flags.AGENT_ENABLED", False):
        res = _run(tool.execute({"value": "hello"}))
        assert res["ok"] is False
        assert res["error"] == "agent_disabled"
    # 2. Success case
    with patch("app.core.feature_flags.AGENT_ENABLED", True):
        res = _run(tool.execute({"value": "hello"}))
        assert res["ok"] is True
        assert res["data"] == "hello"
    # 3. Exception case
    with patch("app.core.feature_flags.AGENT_ENABLED", True):
        res = _run(tool.execute({"fail": True}))
        assert res["ok"] is False
        assert "Test failure" in res["error"]

# Test 2: Tool registry registration and whitelist filtering
def test_registry_register_and_list():
    registry = ToolRegistry()
    t1 = MockTool()
    t2 = EmailOsintTool()
    registry.register(t1)
    registry.register(t2)
    
    mock_settings = MagicMock()
    mock_settings.AGENT_TOOL_WHITELIST = "email_osint"
    with patch("app.services.agent.registry.settings", mock_settings):
        available = registry.list_available()
        assert len(available) == 1
        assert available[0].name == "email_osint"
        
        assert registry.get("mock_tool") is None
        assert registry.get("email_osint") is not None

# Test 3: Budget enforcer daily quota limit
def test_budget_enforcer_quota():
    enforcer = BudgetEnforcer()
    mock_settings = MagicMock()
    mock_settings.AGENT_DAILY_TOOL_QUOTA = 2
    mock_settings.AGENT_SESSION_MAX_TOOL_CALLS = 10
    mock_settings.AGENT_DAILY_BUDGET_USD = 5.0
    
    with patch("app.services.agent.budget.settings", mock_settings):
        assert enforcer.check_and_consume("email_osint") is True
        assert enforcer.check_and_consume("email_osint") is True
        assert enforcer.check_and_consume("email_osint") is False

# Test 4: Budget enforcer session call limit
def test_budget_enforcer_session():
    enforcer = BudgetEnforcer()
    mock_settings = MagicMock()
    mock_settings.AGENT_DAILY_TOOL_QUOTA = 100
    mock_settings.AGENT_SESSION_MAX_TOOL_CALLS = 2
    mock_settings.AGENT_DAILY_BUDGET_USD = 5.0
    
    with patch("app.services.agent.budget.settings", mock_settings):
        assert enforcer.check_and_consume("email_osint", session_id="sess_1") is True
        assert enforcer.check_and_consume("email_osint", session_id="sess_1") is True
        assert enforcer.check_and_consume("email_osint", session_id="sess_1") is False
        assert enforcer.check_and_consume("email_osint", session_id="sess_2") is True

# Test 5: Budget enforcer daily dollar budget spend limit
def test_budget_enforcer_spend():
    enforcer = BudgetEnforcer()
    mock_settings = MagicMock()
    mock_settings.AGENT_DAILY_TOOL_QUOTA = 100
    mock_settings.AGENT_SESSION_MAX_TOOL_CALLS = 100
    mock_settings.AGENT_DAILY_BUDGET_USD = 0.50
    
    with patch("app.services.agent.budget.settings", mock_settings):
        assert enforcer.check_and_consume("email_osint") is True
        assert enforcer.check_and_consume("email_osint") is False

# Test 6: Budget enforcer daily UTC reset logic
def test_budget_enforcer_reset():
    enforcer = BudgetEnforcer()
    mock_settings = MagicMock()
    mock_settings.AGENT_DAILY_TOOL_QUOTA = 1
    mock_settings.AGENT_SESSION_MAX_TOOL_CALLS = 10
    mock_settings.AGENT_DAILY_BUDGET_USD = 5.0
    
    with patch("app.services.agent.budget.settings", mock_settings):
        assert enforcer.check_and_consume("email_osint") is True
        assert enforcer.check_and_consume("email_osint") is False
        
        enforcer.last_reset_date = date(2020, 1, 1)
        assert enforcer.check_and_consume("email_osint") is True

# Test 7: Audit Logger SQLite db logging and query
def test_audit_logger(tmp_path):
    db_file = tmp_path / "test_audit.db"
    logger = AuditLogger(db_path=str(db_file))
    
    async def run_test():
        await logger.log_tool_call("session_x", "email_osint", {"email": "test@example.com"}, {"ok": True})
        logs = await logger.get_logs("session_x")
        assert len(logs) == 1
        assert logs[0]["tool"] == "email_osint"
        assert logs[0]["params"] == {"email": "test@example.com"}
        assert logs[0]["result"] == {"ok": True}
        
        logs_all = await logger.get_logs()
        assert len(logs_all) == 1
        
    _run(run_test())

# Test 8: Email OSINT and Phone Lookup tools
def test_email_and_phone_tools():
    # Email OSINT Tool
    email_tool = EmailOsintTool()
    email_response = MagicMock()
    email_response.status_code = 200
    email_response.json = MagicMock(return_value={"some": "data"})
    mock_client_email = make_mock_client(email_response)
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.services.agent.tools.email_osint.get_client", return_value=mock_client_email):
        res = _run(email_tool.execute({"email": "test@example.com", "smtp": 1}))
        assert res["ok"] is True
        assert res["data"] == {"some": "data"}
        mock_client_email.get.assert_called_once()
        kwargs = mock_client_email.get.call_args[1]
        assert kwargs["params"]["email"] == "test@example.com"
        assert kwargs["params"]["smtp"] == 1

    # Phone Lookup Tool
    phone_tool = PhoneLookupTool()
    phone_response = MagicMock()
    phone_response.status_code = 200
    phone_response.json = MagicMock(return_value={"status": "ok"})
    mock_client_phone = make_mock_client(phone_response)
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.services.agent.tools.phone_lookup.get_client", return_value=mock_client_phone):
        res = _run(phone_tool.execute({"number": "+905554443322"}))
        assert res["ok"] is True
        assert res["data"] == {"status": "ok"}
        mock_client_phone.get.assert_called_once()
        assert mock_client_phone.get.call_args[1]["params"]["number"] == "+905554443322"

# Test 9: Social media scan and Domain lookup tools
def test_social_and_domain_tools():
    # Social Scan Tool
    social_tool = SocialScanTool()
    social_response = MagicMock()
    social_response.status_code = 200
    social_response.json = MagicMock(return_value={"count": 1})
    mock_client_social = make_mock_client(social_response)
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.services.agent.tools.social_scan.get_client", return_value=mock_client_social):
        res = _run(social_tool.execute({"username": "johndoe", "only": "twitter"}))
        assert res["ok"] is True
        assert res["data"] == {"count": 1}
        mock_client_social.get.assert_called_once()
        assert mock_client_social.get.call_args[1]["params"]["username"] == "johndoe"
        assert mock_client_social.get.call_args[1]["params"]["only"] == "twitter"

    # Domain Lookup Tool
    domain_tool = DomainLookupTool()
    domain_response = MagicMock()
    domain_response.status_code = 200
    domain_response.json = MagicMock(return_value={"whois": "data"})
    mock_client_domain = make_mock_client(domain_response)
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.services.agent.tools.domain_lookup.get_client", return_value=mock_client_domain):
        res = _run(domain_tool.execute({"target": "example.com"}))
        assert res["ok"] is True
        assert res["data"] == {"whois": "data"}
        mock_client_domain.get.assert_called_once()
        assert mock_client_domain.get.call_args[1]["params"]["target"] == "example.com"

# Test 10: Graph query, confidence build, temporal intelligence, and pivot tools
def test_graph_and_temporal_tools():
    # Confidence Build Tool
    conf_tool = ConfidenceBuildTool()
    conf_response = MagicMock()
    conf_response.status_code = 200
    conf_response.json = MagicMock(return_value={"nodes": []})
    mock_client_conf = make_mock_client(conf_response)
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.services.agent.tools.confidence_build.get_client", return_value=mock_client_conf):
        res = _run(conf_tool.execute({"seed_key": "abc", "raw": {"key": "val"}, "ttl_hours": 2.5}))
        assert res["ok"] is True
        assert res["data"] == {"nodes": []}
        mock_client_conf.post.assert_called_once()
        json_data = mock_client_conf.post.call_args[1]["json"]
        assert json_data["seed_key"] == "abc"
        assert json_data["raw"] == {"key": "val"}
        assert json_data["ttl_hours"] == 2.5

    # Temporal Analyze Tool
    temp_tool = TemporalAnalyzeTool()
    temp_response = MagicMock()
    temp_response.status_code = 200
    temp_response.json = MagicMock(return_value={"anomalies": []})
    mock_client_temp = make_mock_client(temp_response)
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.services.agent.tools.temporal_analyze.get_client", return_value=mock_client_temp):
        res = _run(temp_tool.execute({"seed_key": "abc", "narrative": True, "force": True}))
        assert res["ok"] is True
        assert res["data"] == {"anomalies": []}
        mock_client_temp.post.assert_called_once()
        json_data = mock_client_temp.post.call_args[1]["json"]
        assert json_data["seed_key"] == "abc"
        assert json_data["narrative"] is True
        assert json_data["force"] is True

    # Pivot Run Tool
    pivot_tool = PivotRunTool()
    pivot_response = MagicMock()
    pivot_response.status_code = 200
    pivot_response.json = MagicMock(return_value={"session_id": "xyz"})
    mock_client_pivot = make_mock_client(pivot_response)
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.services.agent.tools.pivot_run.get_client", return_value=mock_client_pivot):
        res = _run(pivot_tool.execute({"seed_finding_id": "f1", "seed_key": "abc", "strategies": ["email"]}))
        assert res["ok"] is True
        assert res["data"] == {"session_id": "xyz"}
        mock_client_pivot.post.assert_called_once()
        json_data = mock_client_pivot.post.call_args[1]["json"]
        assert json_data["seed_finding_id"] == "f1"
        assert json_data["seed_key"] == "abc"
        assert json_data["strategies"] == ["email"]

    # Graph Query Tool
    graph_tool = GraphQueryTool()
    graph_response = MagicMock()
    graph_response.status_code = 200
    graph_response.json = MagicMock(return_value={"rows": []})
    mock_client_graph = make_mock_client(graph_response)
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.services.agent.tools.graph_query.get_client", return_value=mock_client_graph):
        res = _run(graph_tool.execute({"query": "MATCH (n) RETURN n LIMIT 5"}))
        assert res["ok"] is True
        assert res["data"] == {"rows": []}
        mock_client_graph.post.assert_called_once()
        json_data = mock_client_graph.post.call_args[1]["json"]
        assert json_data["query"] == "MATCH (n) RETURN n LIMIT 5"
