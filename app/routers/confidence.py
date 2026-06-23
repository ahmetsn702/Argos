# app/routers/confidence.py
"""Confidence Graph API endpoints."""

import threading
import time
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from app.models.confidence import ConfidenceGraph
from app.services.confidence.cache import default_cache

router = APIRouter(prefix="/confidence", tags=["confidence"])

_rate_store: Dict[str, list] = {}
_rate_lock = threading.Lock()


def _check_rate_limit(key: str, max_calls: int,
                      window_seconds: int = 60) -> bool:
    now = time.time()
    with _rate_lock:
        calls = [t for t in _rate_store.get(key, [])
                 if now - t < window_seconds]
        if len(calls) >= max_calls:
            _rate_store[key] = calls
            return True
        calls.append(now)
        _rate_store[key] = calls
        return False


class BuildRequest(BaseModel):
    seed_key: str
    raw: Dict[str, Any] = {}
    ttl_hours: Optional[float] = None


@router.post("/build", response_model=ConfidenceGraph)
def confidence_build(req: BuildRequest):
    if _check_rate_limit(f"build:{req.seed_key}", max_calls=5):
        raise HTTPException(status_code=429,
                            detail="Rate limit: 5 calls/minute")
    try:
        return default_cache.merge_and_save(
            seed_key=req.seed_key,
            raw=req.raw,
            ttl_hours=req.ttl_hours,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/graph", response_model=ConfidenceGraph)
def confidence_graph(
    seed_key: str = Query(..., description="Cache key")
):
    import app.core.feature_flags as _ff
    if _ff.GRAPH_DB_ENABLED:
        try:
            import app.services.graph_db.driver as _gd_driver
            from app.services.graph_db.neo4j_repository import Neo4jRepository
            driver = _gd_driver.get_driver()
            if driver:
                repo = Neo4jRepository(driver)
                import asyncio
                neo4j_graph = asyncio.get_event_loop().run_until_complete(
                    repo.get_graph(seed_key, hops=2)
                )
                if neo4j_graph:
                    return neo4j_graph
        except Exception:
            pass  # fallback: in-memory'ye düş

    graph = default_cache.get(seed_key)
    if graph is None:
        raise HTTPException(status_code=404,
                            detail="Graph not found or expired")
    return graph


@router.get("/finding/{finding_id}")
def confidence_finding(
    finding_id: str,
    seed_key: str = Query(...),
):
    graph = default_cache.get(seed_key)
    if graph is None:
        raise HTTPException(status_code=404,
                            detail="Graph not found")
    finding = graph.findings.get(finding_id)
    if finding is None:
        raise HTTPException(status_code=404,
                            detail=f"Finding '{finding_id}' not found")
    return finding


@router.post("/recompute", response_model=ConfidenceGraph)
def confidence_recompute(req: BuildRequest):
    if _check_rate_limit(f"recompute:{req.seed_key}", max_calls=2):
        raise HTTPException(status_code=429,
                            detail="Rate limit: 2 calls/minute")
    default_cache.invalidate(req.seed_key)
    try:
        return default_cache.merge_and_save(
            seed_key=req.seed_key,
            raw=req.raw,
            ttl_hours=req.ttl_hours,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
