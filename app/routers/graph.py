"""Graph DB debug router (Faz 3.3).

Provides /graph/_shadow_compare/{seed_key} for verifying that Neo4j stays
consistent with the in-memory ConfidenceGraph cache during dual-write.
The endpoint returns {"enabled": false, ...} when GRAPH_DB_ENABLED is off
so it's safe to leave registered in production.
"""

from typing import Any, Dict

from fastapi import APIRouter

router = APIRouter(prefix="/graph", tags=["graph_db"])


@router.get("/_shadow_compare/{seed_key}")
async def shadow_compare(seed_key: str) -> Dict[str, Any]:
    # Lazy imports so that disabling the flag avoids touching graph_db modules.
    from app.core.feature_flags import GRAPH_DB_ENABLED

    if not GRAPH_DB_ENABLED:
        return {"enabled": False, "message": "Graph DB disabled"}

    from app.services.confidence.cache import default_cache
    from app.services.graph_db.driver import get_driver
    from app.services.graph_db.neo4j_repository import Neo4jRepository
    from app.services.graph_db.shadow_reader import ShadowReader

    graph = default_cache.get(seed_key)
    if graph is None:
        return {
            "enabled": True,
            "seed_key": seed_key,
            "memory_nodes": 0,
            "neo4j_nodes": 0,
            "memory_edges": 0,
            "neo4j_edges": 0,
            "in_sync": False,
            "diff": {"only_in_memory": [], "only_in_neo4j": []},
            "message": "No memory graph for seed_key",
        }

    memory_graph = {
        "findings": [{"id": fid} for fid in graph.findings.keys()],
        "edges": [
            {"from": e.source_id, "to": e.target_id} for e in graph.edges
        ],
    }

    repo = Neo4jRepository(get_driver())
    reader = ShadowReader(repo)
    result = await reader.compare_with_memory(seed_key, memory_graph)
    result["enabled"] = True
    return result



# ═══════════════════════════════════════════════════════════════════════════════
# Faz 3.5 — Cypher query endpoints
# ═══════════════════════════════════════════════════════════════════════════════

from fastapi import HTTPException, Query as FQuery
from pydantic import BaseModel


class CypherRequest(BaseModel):
    query: str


def _get_repo():
    """Return (repo, error_response). If disabled/unavailable, repo is None."""
    import app.core.feature_flags as _ff
    if not _ff.GRAPH_DB_ENABLED:
        return None, {"enabled": False}
    from app.services.graph_db.driver import get_driver
    from app.services.graph_db.neo4j_repository import Neo4jRepository
    driver = get_driver()
    if not driver:
        return None, {"enabled": True, "error": "no_driver"}
    return Neo4jRepository(driver), None


@router.get("/neighbors/{finding_id}")
async def graph_neighbors(
    finding_id: str,
    hops: int = FQuery(default=2, ge=1, le=4),
) -> Dict[str, Any]:
    repo, err = _get_repo()
    if err:
        return err
    result = await repo.get_graph(finding_id, hops)
    return {"enabled": True, "finding_id": finding_id, "hops": hops, "data": result}


@router.get("/paths")
async def graph_paths(
    from_id: str = FQuery(...),
    to_id: str = FQuery(...),
    max_hops: int = FQuery(default=4, ge=2, le=6),
) -> Dict[str, Any]:
    repo, err = _get_repo()
    if err:
        return err
    result = await repo.find_paths(from_id, to_id, max_hops)
    return {"enabled": True, "from_id": from_id, "to_id": to_id, "paths": result}


@router.get("/intersect")
async def graph_intersect(
    seed_a: str = FQuery(...),
    seed_b: str = FQuery(...),
) -> Dict[str, Any]:
    repo, err = _get_repo()
    if err:
        return err
    result = await repo.intersect_seeds(seed_a, seed_b)
    return {"enabled": True, "seed_a": seed_a, "seed_b": seed_b, "common": result}


@router.post("/cypher")
async def graph_cypher(req: CypherRequest) -> Dict[str, Any]:
    import app.core.feature_flags as _ff
    if not _ff.GRAPH_DB_ENABLED:
        return {"enabled": False}

    from app.services.graph_db.cypher_guard import CypherGuardError, assert_readonly
    try:
        assert_readonly(req.query)
    except CypherGuardError as e:
        raise HTTPException(status_code=400, detail=str(e))

    from app.services.graph_db.driver import get_driver
    from app.services.graph_db.neo4j_repository import Neo4jRepository
    driver = get_driver()
    if not driver:
        return {"enabled": True, "error": "no_driver"}
    repo = Neo4jRepository(driver)
    result = await repo.query_cypher(req.query, {})
    return {"enabled": True, "rows": result}
