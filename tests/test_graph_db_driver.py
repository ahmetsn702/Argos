"""Tests for Graph DB driver abstraction and repository ABC.

No live Neo4j connection. The neo4j module is replaced via sys.modules
monkeypatch so tests run on machines without the package installed.
"""

import sys
from unittest.mock import MagicMock

import pytest

from app.services.graph_db import driver as driver_mod
from app.services.graph_db.repository_base import GraphRepository


@pytest.fixture(autouse=True)
def _reset_driver_singleton():
    """Clear the driver singleton before and after each test."""
    driver_mod.close_driver()
    yield
    driver_mod.close_driver()


def test_get_driver_returns_none_when_disabled(monkeypatch):
    monkeypatch.setattr(driver_mod.settings, "GRAPH_DB_ENABLED", False)
    assert driver_mod.get_driver() is None


def test_get_driver_singleton(monkeypatch):
    monkeypatch.setattr(driver_mod.settings, "GRAPH_DB_ENABLED", True)

    fake_driver_instance = MagicMock(name="fake_driver_instance")
    fake_GraphDatabase = MagicMock()
    fake_GraphDatabase.driver = MagicMock(return_value=fake_driver_instance)

    fake_neo4j = MagicMock()
    fake_neo4j.GraphDatabase = fake_GraphDatabase
    monkeypatch.setitem(sys.modules, "neo4j", fake_neo4j)

    d1 = driver_mod.get_driver()
    d2 = driver_mod.get_driver()

    assert d1 is d2
    assert d1 is fake_driver_instance
    assert fake_GraphDatabase.driver.call_count == 1


def test_repository_base_is_abstract():
    with pytest.raises(TypeError):
        GraphRepository()  # type: ignore[abstract]


def test_repository_implements_all_methods():
    class ConcreteRepo(GraphRepository):
        async def add_finding(self, finding_id, type, data=None):
            return None

        async def add_edge(self, from_id, to_id, rel_type, weight):
            return None

        async def get_graph(self, seed_id, hops):
            return {}

        async def query_cypher(self, query, params=None):
            return []

        async def find_paths(self, from_id, to_id, max_hops):
            return []

        async def intersect_seeds(self, seed_a, seed_b):
            return []

    repo = ConcreteRepo()
    assert isinstance(repo, GraphRepository)


def test_close_driver_safe_when_none():
    # Fixture already cleared the singleton; calling close_driver again
    # must not raise.
    driver_mod.close_driver()
    driver_mod.close_driver()
