import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ping():
    """Test /__ping endpoint returns 200"""
    response = client.get("/__ping")
    assert response.status_code == 200
    data = response.json()
    assert "ok" in data
    assert data["ok"] is True

