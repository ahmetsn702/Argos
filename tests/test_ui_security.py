# tests/test_ui_security.py
"""API version header ve CORS testleri."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_api_version_header():
    """GET /__ping → X-API-Version: 4.0 header mevcut."""
    r = client.get("/__ping")
    assert r.status_code == 200
    assert r.headers.get("x-api-version") == "4.0"


def test_api_name_header():
    """GET /__ping → X-API-Name: ARGOS-OSINT header mevcut."""
    r = client.get("/__ping")
    assert r.headers.get("x-api-name") == "ARGOS-OSINT"


def test_cors_localhost_allowed():
    """GET /__ping, Origin: http://localhost:8000 → 200."""
    r = client.get("/__ping", headers={"Origin": "http://localhost:8000"})
    assert r.status_code == 200
