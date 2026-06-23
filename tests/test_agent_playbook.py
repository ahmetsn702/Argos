import sys
import uuid
import asyncio
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

from app.services.agent.playbook.parser import PlaybookParser
from app.services.agent.playbook.validator import PlaybookValidator
from app.services.agent.playbook.storage import PlaybookStorage

client = TestClient(app)

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

# ─── Parser Tests ─────────────────────────────────────────────────────────────

def test_parser_regex_fallback_cron():
    with patch("app.services.agent.playbook.parser.settings") as mock_settings:
        mock_settings.GOOGLE_API_KEY = None
        parser = PlaybookParser()
        nl_text = "Name: My Cron Playbook. Run a cron schedule every 5 minutes and raise an alert."
        parsed = _run(parser.parse(nl_text))
        
        assert parsed["name"] == "My Cron Playbook"
        assert parsed["trigger"] == "cron"
        assert parsed["action"] == "alert"
        assert parsed["raw_input"] == nl_text
        assert isinstance(parsed["params"], dict)

def test_parser_regex_fallback_darkweb():
    with patch("app.services.agent.playbook.parser.settings") as mock_settings:
        mock_settings.GOOGLE_API_KEY = None
        parser = PlaybookParser()
        nl_text = "When darkweb has a new breach, execute pivot to find targets at https://example.com/webhook"
        parsed = _run(parser.parse(nl_text))
        
        assert parsed["trigger"] == "darkweb_new_breach"
        assert parsed["action"] == "pivot_run"
        assert parsed["params"]["url"] == "https://example.com/webhook"

def test_parser_regex_fallback_anomaly():
    with patch("app.services.agent.playbook.parser.settings") as mock_settings:
        mock_settings.GOOGLE_API_KEY = None
        parser = PlaybookParser()
        nl_text = "Identify a temporal anomaly and notify webhook. Set threshold of 99.5"
        parsed = _run(parser.parse(nl_text))
        
        assert parsed["trigger"] == "temporal_anomaly"
        assert parsed["action"] == "notify_webhook"
        assert parsed["params"]["threshold"] == 99.5

def test_parser_gemini_success():
    mock_genai = MagicMock()
    mock_client = MagicMock()
    mock_response = MagicMock()
    # Mocking returning a valid JSON string matching the required schema
    mock_response.text = '{"name": "Gemini Playbook", "trigger": "new_platform", "action": "archive", "params": {"key": "val"}}'
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client
    mock_genai.genai = mock_genai

    with patch("app.services.agent.playbook.parser.settings") as mock_settings, \
         patch.dict(sys.modules, {"google": mock_genai, "google.genai": mock_genai}):
        mock_settings.GOOGLE_API_KEY = "fake-api-key"
        
        parser = PlaybookParser()
        parsed = _run(parser.parse("Gemini instruction"))
        
        assert parsed["name"] == "Gemini Playbook"
        assert parsed["trigger"] == "new_platform"
        assert parsed["action"] == "archive"
        assert parsed["params"] == {"key": "val"}

def test_parser_gemini_failure_fallback():
    mock_genai = MagicMock()
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("Gemini service unavailable")
    mock_genai.Client.return_value = mock_client
    mock_genai.genai = mock_genai

    with patch("app.services.agent.playbook.parser.settings") as mock_settings, \
         patch.dict(sys.modules, {"google": mock_genai, "google.genai": mock_genai}):
        mock_settings.GOOGLE_API_KEY = "fake-api-key"
        
        parser = PlaybookParser()
        # Should fallback to regex and correctly parse "darkweb" and "webhook"
        parsed = _run(parser.parse("Monitor darkweb and notify webhook"))
        
        assert parsed["trigger"] == "darkweb_new_breach"
        assert parsed["action"] == "notify_webhook"

# ─── Validator Tests ──────────────────────────────────────────────────────────

def test_validator_valid():
    validator = PlaybookValidator()
    playbook = {
        "name": "Valid Playbook",
        "trigger": "confidence_delta",
        "action": "confidence_build",
        "params": {}
    }
    is_valid, err = validator.validate(playbook)
    assert is_valid is True
    assert err == ""

def test_validator_invalid_cases():
    validator = PlaybookValidator()
    # Missing action
    playbook = {
        "name": "Invalid Playbook",
        "trigger": "confidence_delta"
    }
    is_valid, err = validator.validate(playbook)
    assert is_valid is False
    assert "Missing required field" in err

    # Invalid trigger
    playbook = {
        "name": "Invalid Trigger Playbook",
        "trigger": "invalid_trigger_value",
        "action": "alert"
    }
    is_valid, err = validator.validate(playbook)
    assert is_valid is False
    assert "Invalid trigger" in err

    # Invalid action
    playbook = {
        "name": "Invalid Action Playbook",
        "trigger": "cron",
        "action": "invalid_action_value"
    }
    is_valid, err = validator.validate(playbook)
    assert is_valid is False
    assert "Invalid action" in err

# ─── Storage Tests ────────────────────────────────────────────────────────────

def test_storage_lifecycle():
    storage = PlaybookStorage()
    playbook = {
        "name": "Storage Playbook",
        "trigger": "cron",
        "action": "alert"
    }
    
    # Save
    playbook_id = _run(storage.save(playbook))
    assert isinstance(playbook_id, str)
    assert len(playbook_id) > 0
    
    # Get
    retrieved = _run(storage.get(playbook_id))
    assert retrieved is not None
    assert retrieved["name"] == "Storage Playbook"
    assert retrieved["id"] == playbook_id
    
    # List
    all_playbooks = _run(storage.list_all())
    assert any(p["id"] == playbook_id for p in all_playbooks)
    
    # Delete
    deleted = _run(storage.delete(playbook_id))
    assert deleted is True
    
    # Verify deleted
    assert _run(storage.get(playbook_id)) is None

# ─── Router Tests ─────────────────────────────────────────────────────────────

def test_router_disabled_feature_flag():
    with patch("app.core.feature_flags.AGENT_ENABLED", False):
        # Test parse
        r_parse = client.post("/agent/playbook/parse", json={"nl_text": "run cron"})
        assert r_parse.status_code == 200
        assert r_parse.json() == {"enabled": False}
        
        # Test save
        r_save = client.post("/agent/playbook/save", json={})
        assert r_save.status_code == 200
        assert r_save.json() == {"enabled": False}

def test_router_endpoints_flow():
    with patch("app.core.feature_flags.AGENT_ENABLED", True):
        # 1. Parse
        r_parse = client.post("/agent/playbook/parse", json={"nl_text": "When darkweb breach happens, trigger alert"})
        assert r_parse.status_code == 200
        playbook = r_parse.json()
        assert playbook["trigger"] == "darkweb_new_breach"
        assert playbook["action"] == "alert"
        
        # 2. Save invalid
        invalid_playbook = dict(playbook)
        invalid_playbook["action"] = "invalid_action"
        r_save_invalid = client.post("/agent/playbook/save", json=invalid_playbook)
        assert r_save_invalid.status_code == 400
        assert "error" in r_save_invalid.json()
        
        # 3. Save valid
        r_save_valid = client.post("/agent/playbook/save", json=playbook)
        assert r_save_valid.status_code == 200
        saved_data = r_save_valid.json()
        assert "id" in saved_data
        playbook_id = saved_data["id"]
        
        # 4. List all
        r_list = client.get("/agent/playbook/list")
        assert r_list.status_code == 200
        list_data = r_list.json()
        assert any(p["id"] == playbook_id for p in list_data)
        
        # 5. Delete
        r_delete = client.delete(f"/agent/playbook/{playbook_id}")
        assert r_delete.status_code == 200
        assert r_delete.json() == {"deleted": True}
