"""Integration tests for /temporal/* endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.temporal import TemporalAnalysis
from app.services.temporal.cache import _default_backend

client = TestClient(app)

_SEED = "email:test@x.com"
_NOW = datetime(2024, 1, 1, 0, 0, 0)


def _analysis(seed_key: str = _SEED) -> TemporalAnalysis:
    return TemporalAnalysis(seed_key=seed_key, computed_at=_NOW)


@pytest.fixture(autouse=True)
def reset_state():
    _default_backend.clear()
    from app.routers.temporal import _rate_store
    _rate_store.clear()
    yield
    _default_backend.clear()
    from app.routers.temporal import _rate_store
    _rate_store.clear()


# --- POST /temporal/analyze ---

@patch("app.routers.temporal.analyze", new_callable=AsyncMock)
def test_analyze_404_when_no_graph(mock_analyze):
    mock_analyze.return_value = None
    resp = client.post("/temporal/analyze", json={"seed_key": _SEED})
    assert resp.status_code == 404


@patch("app.routers.temporal.analyze", new_callable=AsyncMock)
def test_analyze_200_returns_analysis(mock_analyze):
    mock_analyze.return_value = _analysis()
    resp = client.post("/temporal/analyze", json={"seed_key": _SEED})
    assert resp.status_code == 200
    data = resp.json()
    assert data["seed_key"] == _SEED
    assert data["events"] == []
    assert data["anomalies"] == []
    assert data["narrative"] is None


@patch("app.routers.temporal.analyze", new_callable=AsyncMock)
def test_analyze_rate_limit_429(mock_analyze):
    mock_analyze.return_value = _analysis()
    for _ in range(5):
        client.post("/temporal/analyze", json={"seed_key": _SEED})
    resp = client.post("/temporal/analyze", json={"seed_key": _SEED})
    assert resp.status_code == 429


@patch("app.routers.temporal.analyze", new_callable=AsyncMock)
def test_analyze_force_flag_passed(mock_analyze):
    mock_analyze.return_value = _analysis()
    client.post("/temporal/analyze", json={"seed_key": _SEED, "force": True})
    _, kwargs = mock_analyze.call_args
    assert kwargs.get("force") is True or mock_analyze.call_args[0][2] is True


def test_analyze_missing_seed_key_422():
    resp = client.post("/temporal/analyze", json={})
    assert resp.status_code == 422


# --- GET /temporal/timeline/{seed_key} ---

def test_timeline_404_on_cache_miss():
    resp = client.get(f"/temporal/timeline/{_SEED}")
    assert resp.status_code == 404


def test_timeline_200_on_cache_hit():
    _default_backend.put(_SEED, _analysis(), ttl_seconds=3600)
    resp = client.get(f"/temporal/timeline/{_SEED}")
    assert resp.status_code == 200
    assert resp.json()["seed_key"] == _SEED


# --- GET /temporal/anomalies/{seed_key} ---

def test_anomalies_404_on_cache_miss():
    resp = client.get(f"/temporal/anomalies/{_SEED}")
    assert resp.status_code == 404


def test_anomalies_200_stats_structure():
    _default_backend.put(_SEED, _analysis(), ttl_seconds=3600)
    resp = client.get(f"/temporal/anomalies/{_SEED}")
    assert resp.status_code == 200
    data = resp.json()
    assert data["seed_key"] == _SEED
    assert "anomalies" in data
    assert "stats" in data
    assert "total" in data["stats"]
    assert "by_type" in data["stats"]
    assert "by_severity" in data["stats"]
