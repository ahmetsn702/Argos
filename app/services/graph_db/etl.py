"""ConfidenceGraph -> Neo4j ETL.

Idempotent (MERGE-only) export of findings and edges. Errors are collected
into a list rather than raised at the graph level so partial failures don't
abort the entire export.
"""

import asyncio
from typing import Any, Dict, List, Optional


def _safe_rel_type(rel_type: str) -> str:
    """Return rel_type sanitized for Cypher relationship label.

    Neo4j does not allow parameterized relationship types, so we filter
    to alphanumeric and underscore characters and validate non-empty.
    """
    cleaned = "".join(c for c in (rel_type or "") if c.isalnum() or c == "_")
    if not cleaned:
        raise ValueError(f"Invalid rel_type: {rel_type!r}")
    return cleaned


class ConfidenceGraphToNeo4j:
    """Export a ConfidenceGraph dict into Neo4j using idempotent MERGE."""

    def __init__(self, driver: Optional[Any]) -> None:
        self.driver = driver

    async def export_finding(self, finding: Dict[str, Any]) -> None:
        """Insert or update a single Finding node (MERGE on id)."""
        if self.driver is None:
            return

        if "id" not in finding:
            raise ValueError("finding must include 'id'")

        props: Dict[str, Any] = {
            "id": finding["id"],
            "type": finding.get("type"),
            "confidence": finding.get("confidence"),
            "value": finding.get("value"),
            "created_at": finding.get("created_at"),
            "source": finding.get("source"),
        }

        cypher = "MERGE (f:Finding {id: $id}) SET f += $props"

        def _run() -> None:
            with self.driver.session() as session:
                session.run(cypher, id=props["id"], props=props)

        await asyncio.to_thread(_run)

    async def export_edge(
        self,
        from_id: str,
        to_id: str,
        rel_type: str,
        weight: float,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """Insert or update a relationship between two existing findings.

        Raises ValueError if either node is missing. Caller (export_graph)
        is expected to catch and log into errors list.
        """
        if self.driver is None:
            return

        safe_rel = _safe_rel_type(rel_type)
        meta = metadata or {}

        check_cypher = (
            "MATCH (a:Finding {id: $from_id}) "
            "MATCH (b:Finding {id: $to_id}) "
            "RETURN count(a) AS ca, count(b) AS cb"
        )
        merge_cypher = (
            "MATCH (a:Finding {id: $from_id}) "
            "MATCH (b:Finding {id: $to_id}) "
            f"MERGE (a)-[r:{safe_rel}]->(b) "
            "SET r.weight = $weight, r.metadata = $metadata"
        )

        def _run() -> None:
            with self.driver.session() as session:
                check = session.run(
                    check_cypher, from_id=from_id, to_id=to_id
                ).single()
                if check is None or check.get("ca", 0) == 0 or check.get("cb", 0) == 0:
                    raise ValueError(
                        f"edge endpoints missing: {from_id} -> {to_id}"
                    )
                session.run(
                    merge_cypher,
                    from_id=from_id,
                    to_id=to_id,
                    weight=weight,
                    metadata=meta,
                )

        await asyncio.to_thread(_run)

    async def export_graph(self, graph: Dict[str, Any]) -> Dict[str, Any]:
        """Export a graph dict {findings: [...], edges: [...]}.

        Returns a counts/errors summary; never raises at this level.
        """
        nodes_written = 0
        edges_written = 0
        errors: List[str] = []

        if self.driver is None:
            return {
                "nodes_written": nodes_written,
                "edges_written": edges_written,
                "errors": errors,
            }

        for finding in graph.get("findings", []) or []:
            try:
                await self.export_finding(finding)
                nodes_written += 1
            except Exception as e:
                errors.append(f"finding {finding.get('id', '?')}: {e}")

        for edge in graph.get("edges", []) or []:
            try:
                await self.export_edge(
                    edge["from"],
                    edge["to"],
                    edge.get("rel_type", "RELATED"),
                    float(edge.get("weight", 1.0)),
                    edge.get("metadata"),
                )
                edges_written += 1
            except Exception as e:
                errors.append(
                    f"edge {edge.get('from', '?')} -> {edge.get('to', '?')}: {e}"
                )

        return {
            "nodes_written": nodes_written,
            "edges_written": edges_written,
            "errors": errors,
        }


__all__ = ["ConfidenceGraphToNeo4j"]
