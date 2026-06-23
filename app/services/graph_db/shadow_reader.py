"""Shadow reader — compares an in-memory ConfidenceGraph snapshot with the
Neo4j-backed copy during the dual-write phase.

Used by the debug endpoint /graph/_shadow_compare/{seed_key} to verify that
Neo4j is staying consistent with the legacy in-memory cache. The reader
never raises on mismatch; it returns a structured diff report instead.
"""

from typing import Any, Dict, List

from app.services.graph_db.repository_base import GraphRepository


class ShadowReader:
    """Compute a node-level diff between memory and Neo4j graphs."""

    def __init__(self, neo4j_repo: GraphRepository) -> None:
        self.neo4j_repo = neo4j_repo

    async def compare_with_memory(
        self,
        seed_key: str,
        memory_graph: Dict[str, Any],
    ) -> Dict[str, Any]:
        memory_findings = memory_graph.get("findings", []) or []
        memory_edges = memory_graph.get("edges", []) or []
        memory_node_ids = {
            f.get("id") for f in memory_findings if f and f.get("id")
        }

        try:
            neo4j_graph = await self.neo4j_repo.get_graph(seed_key, hops=10)
        except Exception:
            neo4j_graph = {}

        # Driver disabled or seed absent in Neo4j -> empty dict.
        if not neo4j_graph:
            return {
                "seed_key": seed_key,
                "memory_nodes": len(memory_node_ids),
                "neo4j_nodes": 0,
                "memory_edges": len(memory_edges),
                "neo4j_edges": 0,
                "in_sync": False,
                "diff": {
                    "only_in_memory": sorted(
                        nid for nid in memory_node_ids if nid is not None
                    ),
                    "only_in_neo4j": [],
                },
            }

        neo4j_nodes: List[Dict[str, Any]] = neo4j_graph.get("nodes", []) or []
        neo4j_edges: List[Dict[str, Any]] = neo4j_graph.get("edges", []) or []
        neo4j_node_ids = {
            n.get("id") for n in neo4j_nodes if n and n.get("id")
        }

        only_in_memory = sorted(
            nid for nid in (memory_node_ids - neo4j_node_ids) if nid is not None
        )
        only_in_neo4j = sorted(
            nid for nid in (neo4j_node_ids - memory_node_ids) if nid is not None
        )

        in_sync = (
            memory_node_ids == neo4j_node_ids
            and len(memory_edges) == len(neo4j_edges)
        )

        return {
            "seed_key": seed_key,
            "memory_nodes": len(memory_node_ids),
            "neo4j_nodes": len(neo4j_node_ids),
            "memory_edges": len(memory_edges),
            "neo4j_edges": len(neo4j_edges),
            "in_sync": in_sync,
            "diff": {
                "only_in_memory": only_in_memory,
                "only_in_neo4j": only_in_neo4j,
            },
        }


__all__ = ["ShadowReader"]
