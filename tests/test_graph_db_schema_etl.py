"""Faz 3.2 — Schema, ETL, Neo4jRepository unit tests.

All tests carry @pytest.mark.graph_db so the default CI run
(`-m "not graph_db ..."` from pytest.ini) skips them.
No live Neo4j connection: the driver is a MagicMock with a sync
context-manager session.
"""

import asyncio
from typing import Any, Dict, Optional, Tuple
from unittest.mock import MagicMock

import pytest

from app.services.graph_db.etl import ConfidenceGraphToNeo4j
from app.services.graph_db.neo4j_repository import Neo4jRepository
from app.services.graph_db.schema import (
    create_constraints,
    create_indexes,
)


pytestmark = pytest.mark.graph_db


def _run(coro):
    """Mirror the pattern used elsewhere in this codebase."""
    return asyncio.get_event_loop().run_until_complete(coro)


def _build_mock_driver(
    single_return: Optional[Dict[str, Any]] = None,
) -> Tuple[MagicMock, MagicMock]:
    """Return (driver, session) where session.run is observable.

    `single_return` controls what session.run(...).single() returns; useful
    for the existence-check query inside export_edge.
    """
    session = MagicMock(name="session")

    result = MagicMock(name="result")
    result.single = MagicMock(return_value=single_return)
    # Iterating a result yields nothing by default.
    result.__iter__ = lambda self: iter([])
    session.run = MagicMock(name="session.run", return_value=result)

    cm = MagicMock(name="session_cm")
    cm.__enter__ = MagicMock(return_value=session)
    cm.__exit__ = MagicMock(return_value=False)

    driver = MagicMock(name="driver")
    driver.session = MagicMock(return_value=cm)
    return driver, session


# --------------------------------------------------------------------------
# schema.py
# --------------------------------------------------------------------------

def test_create_constraints_calls_driver():
    driver, session = _build_mock_driver()
    _run(create_constraints(driver))

    assert session.run.call_count == 2
    cyphers = [call.args[0] for call in session.run.call_args_list]
    assert all("CONSTRAINT" in c for c in cyphers)
    # Constraints should target Finding and Entity uniqueness.
    joined = " ".join(cyphers)
    assert "Finding" in joined
    assert "Entity" in joined


def test_create_indexes_calls_driver():
    driver, session = _build_mock_driver()
    _run(create_indexes(driver))

    # Four indexes: Finding.type, Finding.confidence, Finding.created_at,
    # Entity.platform.
    assert session.run.call_count == 4
    cyphers = [call.args[0] for call in session.run.call_args_list]
    assert all("INDEX" in c for c in cyphers)


# --------------------------------------------------------------------------
# etl.py
# --------------------------------------------------------------------------

def test_export_finding_merge_idempotent():
    driver, session = _build_mock_driver()
    etl = ConfidenceGraphToNeo4j(driver)
    finding = {
        "id": "f1",
        "type": "email",
        "confidence": 0.8,
        "value": "a@b.c",
    }

    _run(etl.export_finding(finding))
    _run(etl.export_finding(finding))  # second call, same id

    # Two attempts -> two session.run calls; both must use MERGE on Finding.id.
    assert session.run.call_count == 2
    for call in session.run.call_args_list:
        cypher = call.args[0]
        assert "MERGE" in cypher
        assert "Finding" in cypher
        assert "$id" in cypher
        # Must not use CREATE (would violate idempotency).
        assert "CREATE " not in cypher


def test_export_edge_requires_existing_nodes():
    # Existence check returns zero counts -> export_edge raises -> error captured.
    driver, _session = _build_mock_driver(single_return={"ca": 0, "cb": 0})
    etl = ConfidenceGraphToNeo4j(driver)

    graph = {
        "findings": [],
        "edges": [
            {
                "from": "missing_a",
                "to": "missing_b",
                "rel_type": "RELATED",
                "weight": 1.0,
            }
        ],
    }
    result = _run(etl.export_graph(graph))

    assert result["nodes_written"] == 0
    assert result["edges_written"] == 0
    assert len(result["errors"]) == 1
    assert "missing" in result["errors"][0].lower()


def test_export_graph_returns_counts():
    # Existence check returns positive counts so MERGE-edge proceeds.
    driver, _session = _build_mock_driver(single_return={"ca": 1, "cb": 1})
    etl = ConfidenceGraphToNeo4j(driver)

    graph = {
        "findings": [
            {"id": "f1", "type": "email", "confidence": 0.9, "value": "a@b.c"},
            {"id": "f2", "type": "phone", "confidence": 0.8, "value": "+1"},
        ],
        "edges": [
            {"from": "f1", "to": "f2", "rel_type": "RELATED", "weight": 0.5},
        ],
    }
    result = _run(etl.export_graph(graph))

    assert result == {
        "nodes_written": 2,
        "edges_written": 1,
        "errors": [],
    }


# --------------------------------------------------------------------------
# neo4j_repository.py — disabled-driver behavior
# --------------------------------------------------------------------------

def test_neo4j_repository_add_finding_disabled():
    repo = Neo4jRepository(driver=None)
    # Must not raise; effectively a no-op.
    _run(repo.add_finding("f1", "email", {"value": "a@b.c"}))


def test_neo4j_repository_get_graph_disabled():
    repo = Neo4jRepository(driver=None)
    result = _run(repo.get_graph("seed1", hops=2))
    assert result == {}


def test_neo4j_repository_query_cypher_disabled():
    repo = Neo4jRepository(driver=None)
    result = _run(repo.query_cypher("MATCH (n) RETURN n", {}))
    assert result == []
