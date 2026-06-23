"""Faz 3.3 — Dual-write + Shadow Reader tests.

The first 3 tests run in CI default (no marker). The remaining 4 carry
@pytest.mark.graph_db and are skipped by default.
"""

import asyncio

import pytest

from app.services.confidence.cache import (
    ConfidenceGraphCache,
    _MemoryBackend,
)


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


# --------------------------------------------------------------------------
# CI default — no marker
# --------------------------------------------------------------------------

def test_merge_and_save_unchanged_when_disabled(monkeypatch):
    """flag=false: merge_and_save returns a graph; Neo4j path untouched."""
    import app.core.feature_flags as ff
    import app.services.graph_db.driver as driver_mod

    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", False)

    driver_calls = []

    def _spy_get_driver():
        driver_calls.append(1)
        return None

    monkeypatch.setattr(driver_mod, "get_driver", _spy_get_driver)

    backend = _MemoryBackend()
    cache = ConfidenceGraphCache(backend)
    graph = cache.merge_and_save("test_seed_disabled", {})

    assert graph is not None
    assert graph.seed_key == "test_seed_disabled"
    # Flag off -> the dual-write block never reaches get_driver().
    assert len(driver_calls) == 0


def test_merge_and_save_calls_neo4j_when_enabled(monkeypatch):
    """flag=true: ConfidenceGraphToNeo4j.export_graph is invoked exactly once."""
    import app.core.feature_flags as ff
    import app.services.graph_db.driver as driver_mod
    import app.services.graph_db.etl as etl_mod

    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", True)

    fake_driver = object()
    monkeypatch.setattr(driver_mod, "get_driver", lambda: fake_driver)

    export_calls = []

    class _FakeETL:
        def __init__(self, driver):
            self.driver = driver

        async def export_graph(self, graph_dict):
            export_calls.append(graph_dict)
            return {
                "nodes_written": len(graph_dict.get("findings", [])),
                "edges_written": len(graph_dict.get("edges", [])),
                "errors": [],
            }

    monkeypatch.setattr(etl_mod, "ConfidenceGraphToNeo4j", _FakeETL)

    backend = _MemoryBackend()
    cache = ConfidenceGraphCache(backend)
    graph = cache.merge_and_save("test_seed_enabled", {})

    assert graph is not None
    assert len(export_calls) == 1
    payload = export_calls[0]
    assert "findings" in payload
    assert "edges" in payload


def test_merge_and_save_neo4j_error_doesnt_raise(monkeypatch):
    """A Neo4j-side exception is swallowed; the legacy result still returns."""
    import app.core.feature_flags as ff
    import app.services.graph_db.driver as driver_mod
    import app.services.graph_db.etl as etl_mod

    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", True)
    monkeypatch.setattr(driver_mod, "get_driver", lambda: object())

    class _BoomETL:
        def __init__(self, driver):
            self.driver = driver

        async def export_graph(self, graph_dict):
            raise RuntimeError("Neo4j is down")

    monkeypatch.setattr(etl_mod, "ConfidenceGraphToNeo4j", _BoomETL)

    backend = _MemoryBackend()
    cache = ConfidenceGraphCache(backend)
    # Must not raise.
    graph = cache.merge_and_save("test_seed_error", {})
    assert graph is not None
    assert graph.seed_key == "test_seed_error"


# --------------------------------------------------------------------------
# graph_db marker — skipped by default CI
# --------------------------------------------------------------------------

@pytest.mark.graph_db
def test_shadow_reader_in_sync():
    from app.services.graph_db.shadow_reader import ShadowReader

    class _FakeRepo:
        async def get_graph(self, seed_id, hops):
            return {
                "nodes": [{"id": "f1"}, {"id": "f2"}],
                "edges": [{"from": "f1", "to": "f2"}],
            }

    reader = ShadowReader(_FakeRepo())
    memory_graph = {
        "findings": [{"id": "f1"}, {"id": "f2"}],
        "edges": [{"from": "f1", "to": "f2"}],
    }
    result = _run(reader.compare_with_memory("seed_a", memory_graph))

    assert result["seed_key"] == "seed_a"
    assert result["memory_nodes"] == 2
    assert result["neo4j_nodes"] == 2
    assert result["memory_edges"] == 1
    assert result["neo4j_edges"] == 1
    assert result["in_sync"] is True
    assert result["diff"]["only_in_memory"] == []
    assert result["diff"]["only_in_neo4j"] == []


@pytest.mark.graph_db
def test_shadow_reader_diff_detected():
    from app.services.graph_db.shadow_reader import ShadowReader

    class _FakeRepo:
        async def get_graph(self, seed_id, hops):
            return {
                "nodes": [{"id": "f1"}, {"id": "f2"}],
                "edges": [],
            }

    reader = ShadowReader(_FakeRepo())
    memory_graph = {
        "findings": [{"id": "f1"}, {"id": "f2"}, {"id": "f3"}],
        "edges": [],
    }
    result = _run(reader.compare_with_memory("seed_b", memory_graph))

    assert result["memory_nodes"] == 3
    assert result["neo4j_nodes"] == 2
    assert result["in_sync"] is False
    assert "f3" in result["diff"]["only_in_memory"]
    assert result["diff"]["only_in_neo4j"] == []


@pytest.mark.graph_db
def test_shadow_reader_driver_none():
    """When Neo4jRepository's driver is None, get_graph returns {}."""
    from app.services.graph_db.neo4j_repository import Neo4jRepository
    from app.services.graph_db.shadow_reader import ShadowReader

    repo = Neo4jRepository(driver=None)
    reader = ShadowReader(repo)
    memory_graph = {"findings": [{"id": "f1"}], "edges": []}
    result = _run(reader.compare_with_memory("seed_c", memory_graph))

    assert result["neo4j_nodes"] == 0
    assert result["in_sync"] is False
    assert "f1" in result["diff"]["only_in_memory"]


@pytest.mark.graph_db
def test_shadow_compare_endpoint_disabled(monkeypatch):
    """GET /graph/_shadow_compare/{seed_key} returns disabled stub."""
    from fastapi.testclient import TestClient

    import app.core.feature_flags as ff
    monkeypatch.setattr(ff, "GRAPH_DB_ENABLED", False)

    from app.main import app
    client = TestClient(app)
    response = client.get("/graph/_shadow_compare/test_seed")

    assert response.status_code == 200
    body = response.json()
    assert body == {"enabled": False, "message": "Graph DB disabled"}
