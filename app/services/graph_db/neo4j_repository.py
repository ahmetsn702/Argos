"""Concrete Neo4j repository implementing the GraphRepository ABC.

When driver is None (feature flag disabled or neo4j package missing),
every method returns the safe empty value for its signature without
raising. Callers can therefore wire this in unconditionally.
"""

import asyncio
from typing import Any, Dict, List, Optional

from app.services.graph_db.driver import get_driver
from app.services.graph_db.repository_base import GraphRepository


def _safe_rel_type(rel_type: str) -> str:
    cleaned = "".join(c for c in (rel_type or "") if c.isalnum() or c == "_")
    if not cleaned:
        raise ValueError(f"Invalid rel_type: {rel_type!r}")
    return cleaned


class Neo4jRepository(GraphRepository):
    """Async wrapper over the synchronous neo4j Bolt driver."""

    def __init__(self, driver: Optional[Any] = None) -> None:
        # Explicit None means "disabled / not configured". Callers that want
        # the singleton driver should pass get_driver() explicitly.
        self._driver = driver

    @property
    def driver(self) -> Optional[Any]:
        return self._driver

    async def add_finding(
        self,
        finding_id: str,
        type: str,
        data: Optional[Dict[str, Any]] = None,
    ) -> None:
        if self._driver is None:
            return

        props: Dict[str, Any] = {"id": finding_id, "type": type}
        if data:
            props.update(data)

        cypher = "MERGE (f:Finding {id: $id}) SET f += $props"

        def _run() -> None:
            with self._driver.session() as session:
                session.run(cypher, id=finding_id, props=props)

        await asyncio.to_thread(_run)

    async def add_edge(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        weight: float,
    ) -> None:
        if self._driver is None:
            return

        safe_rel = _safe_rel_type(rel_type)
        cypher = (
            "MATCH (a:Finding {id: $from_id}) "
            "MATCH (b:Finding {id: $to_id}) "
            f"MERGE (a)-[r:{safe_rel}]->(b) "
            "SET r.weight = $weight"
        )

        def _run() -> None:
            with self._driver.session() as session:
                session.run(
                    cypher, from_id=from_id, to_id=to_id, weight=weight
                )

        await asyncio.to_thread(_run)

    async def get_graph(self, seed_id: str, hops: int) -> Dict[str, Any]:
        if self._driver is None:
            return {}

        hops_safe = max(0, int(hops))
        cypher = (
            "MATCH (seed:Finding {id: $seed_id}) "
            f"OPTIONAL MATCH path = (seed)-[*0..{hops_safe}]-(other) "
            "WITH seed, "
            "     collect(DISTINCT other) AS others, "
            "     collect(DISTINCT relationships(path)) AS rel_lists "
            "RETURN seed AS seed, others AS others, rel_lists AS rel_lists"
        )

        def _run() -> Dict[str, Any]:
            with self._driver.session() as session:
                result = session.run(cypher, seed_id=seed_id)
                rec = result.single()
                if rec is None:
                    return {}
                seed_node = rec.get("seed")
                others = rec.get("others") or []
                rel_lists = rec.get("rel_lists") or []

                nodes: List[Dict[str, Any]] = []
                if seed_node is not None:
                    nodes.append(_node_to_dict(seed_node))
                for n in others:
                    if n is None:
                        continue
                    nodes.append(_node_to_dict(n))

                edges: List[Dict[str, Any]] = []
                for rels in rel_lists:
                    if not rels:
                        continue
                    for rel in rels:
                        edges.append(_rel_to_dict(rel))

                return {"nodes": nodes, "edges": edges}

        return await asyncio.to_thread(_run)

    async def query_cypher(
        self,
        query: str,
        params: Optional[Dict[str, Any]] = None,
    ) -> List[Dict[str, Any]]:
        if self._driver is None:
            return []

        params = params or {}

        def _run() -> List[Dict[str, Any]]:
            with self._driver.session() as session:
                result = session.run(query, **params)
                return [dict(r) for r in result]

        return await asyncio.to_thread(_run)

    async def find_paths(
        self,
        from_id: str,
        to_id: str,
        max_hops: int,
    ) -> List[List[Dict[str, Any]]]:
        if self._driver is None:
            return []

        hops_safe = max(1, int(max_hops))
        cypher = (
            "MATCH path = shortestPath("
            f"(a:Finding {{id: $from_id}})-[*..{hops_safe}]-(b:Finding {{id: $to_id}})"
            ") RETURN [n IN nodes(path) | n] AS nodes_in_path"
        )

        def _run() -> List[List[Dict[str, Any]]]:
            with self._driver.session() as session:
                result = session.run(cypher, from_id=from_id, to_id=to_id)
                paths: List[List[Dict[str, Any]]] = []
                for rec in result:
                    nodes_in_path = rec.get("nodes_in_path") or []
                    paths.append([_node_to_dict(n) for n in nodes_in_path])
                return paths

        return await asyncio.to_thread(_run)

    async def intersect_seeds(
        self,
        seed_a: str,
        seed_b: str,
    ) -> List[Dict[str, Any]]:
        if self._driver is None:
            return []

        cypher = (
            "MATCH (a:Finding {seed_key: $seed_a})-[*1..3]-(common:Finding) "
            "WITH DISTINCT common "
            "MATCH (b:Finding {seed_key: $seed_b})-[*1..3]-(common) "
            "RETURN DISTINCT common "
            "ORDER BY common.confidence DESC LIMIT 50"
        )

        def _run() -> List[Dict[str, Any]]:
            with self._driver.session() as session:
                result = session.run(cypher, seed_a=seed_a, seed_b=seed_b)
                rows: List[Dict[str, Any]] = []
                for rec in result:
                    common = rec.get("common")
                    if common is not None:
                        rows.append(_node_to_dict(common))
                return rows

        return await asyncio.to_thread(_run)


def _node_to_dict(node: Any) -> Dict[str, Any]:
    """Best-effort conversion of a neo4j Node (or mock) to a dict."""
    try:
        return dict(node)
    except Exception:
        return {"_repr": repr(node)}


def _rel_to_dict(rel: Any) -> Dict[str, Any]:
    """Best-effort conversion of a neo4j Relationship to a dict."""
    try:
        out = dict(rel)
    except Exception:
        out = {}
    rel_type = getattr(rel, "type", None)
    if rel_type is not None:
        out["_type"] = rel_type
    return out


__all__ = ["Neo4jRepository"]
