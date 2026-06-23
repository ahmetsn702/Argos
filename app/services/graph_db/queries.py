"""Parameterized Cypher query templates for graph endpoints."""

NEIGHBORS_QUERY = (
    "MATCH (start:Finding {id: $finding_id})-[*1..{hops}]-(neighbor) "
    "RETURN DISTINCT neighbor"
)

PATHS_QUERY = (
    "MATCH (a:Finding {{id: $from_id}}), (b:Finding {{id: $to_id}}) "
    "MATCH p = shortestPath((a)-[*..{max_hops}]-(b)) "
    "RETURN p"
)

INTERSECT_QUERY = (
    "MATCH (a:Finding {id: $seed_a})-[]-(common) "
    "MATCH (b:Finding {id: $seed_b})-[]-(common) "
    "RETURN DISTINCT common "
    "ORDER BY common.confidence DESC "
    "LIMIT 50"
)

__all__ = ["NEIGHBORS_QUERY", "PATHS_QUERY", "INTERSECT_QUERY"]
