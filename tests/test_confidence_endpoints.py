# tests/test_confidence_endpoints.py
"""Integration tests for /confidence/* endpoints."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_rate_limit():
    from app.routers.confidence import _rate_store
    _rate_store.clear()
    yield
    _rate_store.clear()


@pytest.fixture(autouse=True)
def reset_cache():
    from app.services.confidence.cache import _default_backend
    _default_backend.clear()
    yield
    _default_backend.clear()


def test_build_returns_200():
    resp = client.post("/confidence/build", json={
        "seed_key": "email:test@x.com",
        "raw": {"mosint": {"email": "test@x.com"}},
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["seed_key"] == "email:test@x.com"
    assert data["version"] == 1


def test_build_twice_increments_version():
    payload = {
        "seed_key": "email:v@x.com",
        "raw": {"mosint": {"email": "v@x.com"}},
        "ttl_hours": 1,
    }
    r1 = client.post("/confidence/build", json=payload)
    r2 = client.post("/confidence/build", json=payload)
    assert r1.json()["version"] == 1
    assert r2.json()["version"] == 2


def test_build_empty_raw():
    resp = client.post("/confidence/build", json={
        "seed_key": "seed:empty",
        "raw": {},
    })
    assert resp.status_code == 200
    assert resp.json()["findings"] == {}


def test_graph_cache_miss_returns_404():
    resp = client.get("/confidence/graph",
                      params={"seed_key": "nonexistent"})
    assert resp.status_code == 404


def test_graph_cache_hit_returns_200():
    client.post("/confidence/build", json={
        "seed_key": "email:hit@x.com",
        "raw": {},
        "ttl_hours": 1,
    })
    resp = client.get("/confidence/graph",
                      params={"seed_key": "email:hit@x.com"})
    assert resp.status_code == 200
    assert resp.json()["seed_key"] == "email:hit@x.com"


def test_finding_not_found_returns_404():
    client.post("/confidence/build", json={
        "seed_key": "seed:nofind",
        "raw": {},
        "ttl_hours": 1,
    })
    resp = client.get(
        "/confidence/finding/email:ghost@x.com",
        params={"seed_key": "seed:nofind"},
    )
    assert resp.status_code == 404


def test_finding_graph_missing_returns_404():
    resp = client.get(
        "/confidence/finding/email:a@x.com",
        params={"seed_key": "missing_graph"},
    )
    assert resp.status_code == 404


def test_finding_exists_returns_200():
    client.post("/confidence/build", json={
        "seed_key": "seed:find",
        "raw": {"mosint": {"email": "find@x.com"}},
        "ttl_hours": 1,
    })
    resp = client.get(
        "/confidence/finding/email:find@x.com",
        params={"seed_key": "seed:find"},
    )
    assert resp.status_code == 200
    assert resp.json()["id"] == "email:find@x.com"


def test_recompute_clears_cache():
    client.post("/confidence/build", json={
        "seed_key": "seed:recomp",
        "raw": {},
        "ttl_hours": 1,
    })
    assert client.get("/confidence/graph",
                      params={"seed_key": "seed:recomp"}).status_code == 200

    resp = client.post("/confidence/recompute", json={
        "seed_key": "seed:recomp",
        "raw": {},
        "ttl_hours": 1,
    })
    assert resp.status_code == 200
    assert resp.json()["version"] == 1


def test_recompute_rate_limit():
    payload = {"seed_key": "seed:rl", "raw": {}}
    client.post("/confidence/recompute", json=payload)
    client.post("/confidence/recompute", json=payload)
    resp = client.post("/confidence/recompute", json=payload)
    assert resp.status_code == 429


def test_build_rate_limit():
    payload = {"seed_key": "seed:rl_build", "raw": {}}
    for _ in range(5):
        client.post("/confidence/build", json=payload)
    resp = client.post("/confidence/build", json=payload)
    assert resp.status_code == 429


def test_confidence_router_in_routes():
    resp = client.get("/__routes")
    assert resp.status_code == 200
    paths = [r["path"] for r in resp.json()]
    confidence_routes = [p for p in paths if p.startswith("/confidence")]
    assert len(confidence_routes) >= 4
