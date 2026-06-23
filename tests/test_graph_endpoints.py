"""Faz 3.5 — Graph Cypher endpoint tests.

6 tests run in CI default (no marker). 4 carry @pytest.mark.graph_db.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ═══════════════════════════════════════════════════════════════════════════════
# CI default — no marker (GRAPH_DB_ENABLED=false by default)
# ═══════════════════════════════════════════════════════════════════════════════

def test_neighbors_disabled(monkeypatch):
    import app.core.feature_flags as ff
    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", False)
    resp = client.get("/graph/neighbors/f1?hops=2")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_paths_disabled(monkeypatch):
    import app.core.feature_flags as ff
    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", False)
    resp = client.get("/graph/paths?from_id=a&to_id=b&max_hops=3")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_intersect_disabled(monkeypatch):
    import app.core.feature_flags as ff
    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", False)
    resp = client.get("/graph/intersect?seed_a=x&seed_b=y")
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_cypher_disabled(monkeypatch):
    import app.core.feature_flags as ff
    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", False)
    resp = client.post("/graph/cypher", json={"query": "MATCH (n) RETURN n"})
    assert resp.status_code == 200
    assert resp.json()["enabled"] is False


def test_cypher_write_blocked(monkeypatch):
    """Write query blocked even when flag is true."""
    import app.core.feature_flags as ff
    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", True)

    resp = client.post("/graph/cypher", json={"query": "CREATE (n:Test)"})
    assert resp.status_code == 400
    assert "Write operations not allowed" in resp.json()["detail"]


def test_cypher_readonly_allowed(monkeypatch):
    """Readonly query passes guard (may fail at driver level, but not 400)."""
    import app.core.feature_flags as ff
    import app.services.graph_db.driver as driver_mod
    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", True)
    monkeypatch.setattr(driver_mod, "get_driver", lambda: None)

    resp = client.post(
        "/graph/cypher",
        json={"query": "MATCH (n) RETURN n LIMIT 5"},
    )
    # No driver → returns no_driver, not 400.
    assert resp.status_code == 200
    body = resp.json()
    assert body.get("error") == "no_driver" or "rows" in body


# ═══════════════════════════════════════════════════════════════════════════════
# @pytest.mark.graph_db — skipped by CI default
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.mark.graph_db
def test_neighbors_returns_data(monkeypatch):
    import app.core.feature_flags as ff
    import app.services.graph_db.driver as driver_mod
    import app.services.graph_db.neo4j_repository as repo_mod

    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", True)
    monkeypatch.setattr(driver_mod, "get_driver", lambda: object())

    class _FakeRepo:
        def __init__(self, driver):
            pass

        async def get_graph(self, seed_id, hops):
            return {"nodes": [{"id": seed_id}], "edges": []}

    monkeypatch.setattr(repo_mod, "Neo4jRepository", _FakeRepo)

    resp = client.get("/graph/neighbors/f1?hops=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["finding_id"] == "f1"
    assert "data" in body


@pytest.mark.graph_db
def test_paths_returns_data(monkeypatch):
    import app.core.feature_flags as ff
    import app.services.graph_db.driver as driver_mod
    import app.services.graph_db.neo4j_repository as repo_mod

    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", True)
    monkeypatch.setattr(driver_mod, "get_driver", lambda: object())

    class _FakeRepo:
        def __init__(self, driver):
            pass

        async def find_paths(self, from_id, to_id, max_hops):
            return [[{"id": from_id}, {"id": to_id}]]

    monkeypatch.setattr(repo_mod, "Neo4jRepository", _FakeRepo)

    resp = client.get("/graph/paths?from_id=a&to_id=b&max_hops=3")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["paths"] == [[{"id": "a"}, {"id": "b"}]]


@pytest.mark.graph_db
def test_intersect_returns_data(monkeypatch):
    import app.core.feature_flags as ff
    import app.services.graph_db.driver as driver_mod
    import app.services.graph_db.neo4j_repository as repo_mod

    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", True)
    monkeypatch.setattr(driver_mod, "get_driver", lambda: object())

    class _FakeRepo:
        def __init__(self, driver):
            pass

        async def intersect_seeds(self, seed_a, seed_b):
            return [{"id": "common1"}]

    monkeypatch.setattr(repo_mod, "Neo4jRepository", _FakeRepo)

    resp = client.get("/graph/intersect?seed_a=x&seed_b=y")
    assert resp.status_code == 200
    body = resp.json()
    assert body["enabled"] is True
    assert body["common"] == [{"id": "common1"}]


@pytest.mark.graph_db
def test_cypher_guard_forbids_merge():
    from app.services.graph_db.cypher_guard import CypherGuardError, assert_readonly

    with pytest.raises(CypherGuardError):
        assert_readonly("MERGE (n:Finding {id: 'x'})")
