"""Integration tests for /pivot/* endpoints."""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.main import app
from app.models.pivot import PivotSession, PivotStatus
from app.services.pivot.session_store import default_session_store

client = TestClient(app)


@pytest.fixture(autouse=True)
def _clear_store():
    default_session_store.clear()
    yield
    default_session_store.clear()


@patch("app.services.pivot.orchestrator.execute_strategies", new_callable=AsyncMock)
def test_run_returns_200(mock_exec):
    mock_exec.return_value = []
    resp = client.post("/pivot/run", json={
        "seed_finding_id": "email:a@x.com",
        "seed_key": "a@x.com",
        "max_depth": 1,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["seed_key"] == "a@x.com"


def test_run_dry_run():
    resp = client.post("/pivot/run", json={
        "seed_finding_id": "email:a@x.com",
        "seed_key": "a@x.com",
        "max_depth": 2,
        "dry_run": True,
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "completed"
    assert data["plan"] is not None
    assert data["nodes_discovered"] == []


def test_session_get_returns_200():
    resp = client.post("/pivot/run", json={
        "seed_finding_id": "email:a@x.com",
        "seed_key": "a@x.com",
        "dry_run": True,
    })
    sid = resp.json()["session_id"]
    resp2 = client.get(f"/pivot/session/{sid}")
    assert resp2.status_code == 200
    assert resp2.json()["session_id"] == sid


def test_session_get_404():
    resp = client.get("/pivot/session/nonexistent")
    assert resp.status_code == 404


def test_history_returns_list():
    client.post("/pivot/run", json={
        "seed_finding_id": "email:a@x.com",
        "seed_key": "a@x.com",
        "dry_run": True,
    })
    resp = client.get("/pivot/history")
    assert resp.status_code == 200
    data = resp.json()
    assert isinstance(data, list)
    assert len(data) == 1


def test_history_respects_limit():
    for i in range(3):
        client.post("/pivot/run", json={
            "seed_finding_id": f"email:u{i}@x.com",
            "seed_key": f"u{i}@x.com",
            "dry_run": True,
        })
    resp = client.get("/pivot/history?limit=2")
    assert resp.status_code == 200
    assert len(resp.json()) == 2


def test_run_validation_error():
    resp = client.post("/pivot/run", json={
        "seed_finding_id": "email:a@x.com",
        "seed_key": "a@x.com",
        "max_depth": 10,  # exceeds max 4
    })
    assert resp.status_code == 422
