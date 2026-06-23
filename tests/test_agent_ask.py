import sys
import uuid
import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ask_disabled():
    with patch("app.core.feature_flags.AGENT_ENABLED", False):
        response = client.post("/agent/ask", json={"query": "test query"})
        assert response.status_code == 200
        assert response.json() == {"enabled": False}

def test_ask_empty_findings():
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.routers.agent_ask.ChromaStore") as mock_store_cls:
        
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store_cls.return_value = mock_store
        
        response = client.post("/agent/ask", json={"query": "test query", "session_id": "test-session"})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "No findings available for this session"
        assert data["sources"] == []
        assert data["session_id"] == "test-session"

def test_ask_no_session_id():
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.routers.agent_ask.ChromaStore") as mock_store_cls:
        
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=[])
        mock_store_cls.return_value = mock_store
        
        response = client.post("/agent/ask", json={"query": "test query"})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "No findings available for this session"
        assert data["sources"] == []
        generated_id = data["session_id"]
        assert uuid.UUID(generated_id)

def test_ask_fallback_answer():
    mock_results = [
        {"text": "Finding one text.", "metadata": {"key": "val1"}, "id": "id1"},
        {"text": "Finding two text.", "metadata": {"key": "val2"}, "id": "id2"}
    ]
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.routers.agent_ask.ChromaStore") as mock_store_cls, \
         patch("app.routers.agent_ask.settings") as mock_settings:
        
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=mock_results)
        mock_store_cls.return_value = mock_store
        mock_settings.GOOGLE_API_KEY = None
        
        response = client.post("/agent/ask", json={"query": "test query", "session_id": "test-session"})
        assert response.status_code == 200
        data = response.json()
        assert "Found 2 relevant source(s)" in data["answer"]
        assert "Finding one text." in data["answer"]
        assert "Finding two text." in data["answer"]
        assert data["sources"] == mock_results
        assert data["session_id"] == "test-session"

def test_ask_gemini_success():
    mock_results = [
        {"text": "Finding one text.", "metadata": {"key": "val1"}, "id": "id1"}
    ]
    
    mock_genai = MagicMock()
    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.text.strip.return_value = "Mocked Gemini Answer"
    mock_client.models.generate_content.return_value = mock_response
    mock_genai.Client.return_value = mock_client
    mock_genai.genai = mock_genai
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.routers.agent_ask.ChromaStore") as mock_store_cls, \
         patch("app.routers.agent_ask.settings") as mock_settings, \
         patch.dict(sys.modules, {"google": mock_genai, "google.genai": mock_genai}):
        
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=mock_results)
        mock_store_cls.return_value = mock_store
        mock_settings.GOOGLE_API_KEY = "dummy-key"
        
        response = client.post("/agent/ask", json={"query": "what is this?", "session_id": "test-session"})
        assert response.status_code == 200
        data = response.json()
        assert data["answer"] == "Mocked Gemini Answer"
        assert data["sources"] == mock_results
        assert data["session_id"] == "test-session"

def test_ask_gemini_fails_fallback():
    mock_results = [
        {"text": "Finding one text.", "metadata": {"key": "val1"}, "id": "id1"}
    ]
    
    mock_genai = MagicMock()
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = Exception("LLM connection error")
    mock_genai.Client.return_value = mock_client
    mock_genai.genai = mock_genai
    
    with patch("app.core.feature_flags.AGENT_ENABLED", True), \
         patch("app.routers.agent_ask.ChromaStore") as mock_store_cls, \
         patch("app.routers.agent_ask.settings") as mock_settings, \
         patch.dict(sys.modules, {"google": mock_genai, "google.genai": mock_genai}):
        
        mock_store = MagicMock()
        mock_store.search = AsyncMock(return_value=mock_results)
        mock_store_cls.return_value = mock_store
        mock_settings.GOOGLE_API_KEY = "dummy-key"
        
        response = client.post("/agent/ask", json={"query": "what is this?", "session_id": "test-session"})
        assert response.status_code == 200
        data = response.json()
        assert "Found 1 relevant source(s)" in data["answer"]
        assert "Finding one text." in data["answer"]
        assert data["sources"] == mock_results
        assert data["session_id"] == "test-session"
