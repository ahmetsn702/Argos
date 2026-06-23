# tests/test_analysis_endpoints.py
"""LLM Analysis endpoint testleri."""
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_analysis_health():
    """GET /analysis/health → 200, status ok."""
    r = client.get("/analysis/health")
    assert r.status_code == 200
    data = r.json()
    assert data.get("status") == "ok"
    assert "model" in data
    assert "api_key" in data


def test_analysis_osint_empty():
    """POST /analysis/osint with empty data → 200 or api_key_missing."""
    stub = {"summary": "no data", "findings": [], "confidence": 0.0}
    with patch("app.routers.llm_analysis.OsintAnalyst") as mock_cls:
        mock_cls.return_value.analyze = AsyncMock(return_value=stub)
        r = client.post("/analysis/osint", json={"data": {}})
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)


def test_analysis_osint_with_target():
    """POST /analysis/osint with target data → 200, response has summary or error."""
    stub = {"summary": "test analysis", "findings": ["finding1"], "confidence": 0.7}
    with patch("app.routers.llm_analysis.OsintAnalyst") as mock_cls:
        mock_cls.return_value.analyze = AsyncMock(return_value=stub)
        r = client.post("/analysis/osint",
                        json={"data": {"target": "test@test.com", "platform": "email"}})
    assert r.status_code == 200
    data = r.json()
    assert "summary" in data or "error" in data
