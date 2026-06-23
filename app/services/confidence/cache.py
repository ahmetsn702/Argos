# app/services/confidence/cache.py
"""TTL-aware in-memory cache for ConfidenceGraph objects."""

import os
import threading
import time
from typing import Any, Dict, Optional, Tuple

from app.models.confidence import ConfidenceGraph
from app.services.confidence.graph import build_graph

_DEFAULT_TTL_HOURS = 24


def _get_ttl_seconds() -> float:
    try:
        return float(os.getenv(
            "CONFIDENCE_TTL_HOURS",
            str(_DEFAULT_TTL_HOURS)
        )) * 3600
    except Exception:
        return _DEFAULT_TTL_HOURS * 3600


class _MemoryBackend:
    def __init__(self):
        self._store: Dict[str, Tuple[float, ConfidenceGraph]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[ConfidenceGraph]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, graph = item
            if expires_at != 0 and time.time() > expires_at:
                del self._store[key]
                return None
            return graph

    def put(self, key: str, graph: ConfidenceGraph,
            ttl_seconds: float) -> None:
        with self._lock:
            expires_at = 0 if ttl_seconds == 0 else time.time() + ttl_seconds
            self._store[key] = (expires_at, graph)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)


class ConfidenceGraphCache:
    def __init__(self, backend: _MemoryBackend = None):
        self._backend = backend or _default_backend

    def get(self, seed_key: str) -> Optional[ConfidenceGraph]:
        return self._backend.get(seed_key)

    def put(self, graph: ConfidenceGraph, ttl_hours: float = None) -> None:
        if ttl_hours is None:
            ttl_seconds = _get_ttl_seconds()
        else:
            ttl_seconds = ttl_hours * 3600
        if ttl_seconds == 0:
            return
        self._backend.put(graph.seed_key, graph, ttl_seconds)

    def invalidate(self, seed_key: str) -> None:
        self._backend.delete(seed_key)

    def merge_and_save(
        self,
        seed_key: str,
        raw: Dict[str, Any],
        ttl_hours: float = None,
    ) -> ConfidenceGraph:
        ttl_seconds = (
            ttl_hours * 3600 if ttl_hours is not None
            else _get_ttl_seconds()
        )
        prior = None
        if ttl_seconds != 0:
            prior = self._backend.get(seed_key)
        graph = build_graph(seed_key, raw, prior=prior)
        if ttl_seconds != 0:
            self._backend.put(seed_key, graph, ttl_seconds)

        # --- Optional Neo4j dual-write ---
        try:
            from app.core.feature_flags import GRAPH_DB_ENABLED
            if GRAPH_DB_ENABLED:
                from app.services.graph_db.driver import get_driver
                from app.services.graph_db.etl import ConfidenceGraphToNeo4j
                driver = get_driver()
                if driver:
                    etl = ConfidenceGraphToNeo4j(driver)
                    graph_dict = _confidence_graph_to_dict(graph)
                    import asyncio
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.ensure_future(etl.export_graph(graph_dict))
                    else:
                        loop.run_until_complete(etl.export_graph(graph_dict))
        except Exception:
            pass  # Neo4j hatası ana akışı asla bozmaz

        return graph


_default_backend = _MemoryBackend()
default_cache = ConfidenceGraphCache(_default_backend)


def _confidence_graph_to_dict(graph: ConfidenceGraph) -> Dict[str, Any]:
    """Convert a ConfidenceGraph Pydantic model to the dict shape expected by
    ConfidenceGraphToNeo4j (keys: 'findings', 'edges').
    """
    findings_out = []
    for fid, f in graph.findings.items():
        ftype = getattr(f.type, "value", None) or str(f.type)
        first_seen = f.first_seen.isoformat() if f.first_seen else None
        sources_summary = (
            ",".join(s.source_id for s in f.sources) if f.sources else None
        )
        findings_out.append({
            "id": fid,
            "type": ftype,
            "value": f.value,
            "confidence": f.confidence_score,
            "created_at": first_seen,
            "source": sources_summary,
        })

    edges_out = []
    for e in graph.edges:
        rtype = getattr(e.edge_type, "value", None) or str(e.edge_type)
        edges_out.append({
            "from": e.source_id,
            "to": e.target_id,
            "rel_type": rtype,
            "weight": e.weight,
            "metadata": dict(e.metadata) if e.metadata else {},
        })

    return {"findings": findings_out, "edges": edges_out}
