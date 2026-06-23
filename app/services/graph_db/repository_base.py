"""Abstract graph repository contract.

Concrete implementations (e.g. Neo4jGraphRepository, InMemoryGraphRepository)
must implement every method declared here. The Strangler Fig migration relies
on this single seam: the routers and services depend on the abstract
GraphRepository, and we swap implementations behind a feature flag without
touching call sites.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional


class GraphRepository(ABC):
    """Async-only graph storage contract."""

    @abstractmethod
    async def add_finding(
        self,
        finding_id: str,
        type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert or update a single Finding node."""
        raise NotImplementedError

    @abstractmethod
    async def add_edge(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        weight: float,
    ) -> None:
        """Insert or update a relationship between two findings."""
        raise NotImplementedError

    @abstractmethod
    async def get_graph(
        self,
        seed_id: str,
        hops: int,
    ) -> Dict[str, Any]:
        """Return the subgraph reachable from `seed_id` within `hops` edges."""
        raise NotImplementedError

    @abstractmethod
    async def query_cypher(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        """Execute a parameterized Cypher query and return result rows."""
        raise NotImplementedError

    @abstractmethod
    async def find_paths(
        self,
        from_id: str,
        to_id: str,
        max_hops: int,
    ) -> List[List[Dict[str, Any]]]:
        """Find paths between two findings, ordered by aggregate confidence."""
        raise NotImplementedError

    @abstractmethod
    async def intersect_seeds(
        self,
        seed_a: str,
        seed_b: str,
    ) -> List[Dict[str, Any]]:
        """Return findings that connect both seed graphs."""
        raise NotImplementedError


__all__ = ["GraphRepository"]
