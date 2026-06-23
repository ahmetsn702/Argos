"""Tests for LLM analysis module."""

import json
from unittest.mock import AsyncMock, patch, MagicMock

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_health_endpoint():
    r = client.get("/analysis/health")
    assert r.status_code == 200
    data = r.json()
    assert "status" in data
    assert data["status"] == "ok"
    assert "model" in data


def test_analyze_no_key():
    with patch("app.services.llm_analyst.settings") as mock_settings:
        mock_settings.GOOGLE_API_KEY = ""
        r = client.post("/analysis/osint", json={"data": {"email": "test@test.com"}})
    assert r.status_code == 200
    assert r.json()["error"] == "api_key_missing"


def test_analyze_mock():
    mock_response = MagicMock()
    mock_response.text = json.dumps({
        "summary": "Test özet",
        "risk_level": "low",
        "key_findings": ["bulgu1"],
        "recommendations": ["öneri1"],
    })

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.services.llm_analyst.settings") as mock_settings, \
         patch("google.genai.Client", return_value=mock_client):
        mock_settings.GOOGLE_API_KEY = "fake-key"
        r = client.post("/analysis/osint", json={"data": {"email": "x@y.com"}})

    assert r.status_code == 200
    data = r.json()
    assert "summary" in data
    assert "risk_level" in data
    assert "key_findings" in data


def test_analyze_empty_data():
    with patch("app.services.llm_analyst.settings") as mock_settings:
        mock_settings.GOOGLE_API_KEY = ""
        r = client.post("/analysis/osint", json={"data": {}})
    assert r.status_code == 200
    # No crash — returns api_key_missing since no key
    assert "error" in r.json()
