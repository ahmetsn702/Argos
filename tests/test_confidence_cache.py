# tests/test_confidence_cache.py
"""Tests for app/services/confidence/cache.py"""

import threading
import time
from datetime import datetime

from app.models.confidence import ConfidenceGraph
from app.services.confidence.cache import ConfidenceGraphCache, _MemoryBackend


def _fresh_cache() -> ConfidenceGraphCache:
    return ConfidenceGraphCache(_MemoryBackend())


def _make_graph(seed_key: str, version: int = 1) -> ConfidenceGraph:
    return ConfidenceGraph(
        seed_key=seed_key,
        findings={},
        edges=[],
        computed_at=datetime(2024, 1, 1, 12, 0, 0),
        version=version,
    )


def test_put_and_get_roundtrip():
    cache = _fresh_cache()
    graph = _make_graph("seed:a@x.com")
    cache.put(graph, ttl_hours=1)
    result = cache.get("seed:a@x.com")
    assert result is not None
    assert result.seed_key == "seed:a@x.com"


def test_get_missing_returns_none():
    cache = _fresh_cache()
    assert cache.get("nonexistent") is None


def test_ttl_expiry():
    backend = _MemoryBackend()
    cache = ConfidenceGraphCache(backend)
    graph = _make_graph("seed:expire")
    backend.put("seed:expire", graph, ttl_seconds=0.05)
    assert cache.get("seed:expire") is not None
    time.sleep(0.1)
    assert cache.get("seed:expire") is None


def test_ttl_zero_disables_cache():
    cache = _fresh_cache()
    graph = _make_graph("seed:zero")
    cache.put(graph, ttl_hours=0)
    assert cache.get("seed:zero") is None


def test_invalidate():
    cache = _fresh_cache()
    graph = _make_graph("seed:inv")
    cache.put(graph, ttl_hours=1)
    assert cache.get("seed:inv") is not None
    cache.invalidate("seed:inv")
    assert cache.get("seed:inv") is None


def test_invalidate_missing_no_error():
    cache = _fresh_cache()
    cache.invalidate("nonexistent")  # should not raise


def test_merge_and_save_first_call():
    cache = _fresh_cache()
    raw = {"mosint": {"email": "a@x.com"}}
    graph = cache.merge_and_save("seed:a@x.com", raw, ttl_hours=1)
    assert graph.version == 1
    assert cache.get("seed:a@x.com") is not None


def test_merge_and_save_second_call_increments_version():
    cache = _fresh_cache()
    raw = {"mosint": {"email": "a@x.com"}}
    g1 = cache.merge_and_save("seed:a@x.com", raw, ttl_hours=1)
    g2 = cache.merge_and_save("seed:a@x.com", raw, ttl_hours=1)
    assert g1.version == 1
    assert g2.version == 2


def test_merge_and_save_ttl_zero_no_cache():
    cache = _fresh_cache()
    raw = {"mosint": {"email": "a@x.com"}}
    graph = cache.merge_and_save("seed:a@x.com", raw, ttl_hours=0)
    assert graph is not None
    assert cache.get("seed:a@x.com") is None


def test_thread_safety():
    cache = _fresh_cache()
    raw = {"mosint": {"email": "a@x.com"}}
    errors = []

    def _worker():
        try:
            cache.merge_and_save("seed:thread", raw, ttl_hours=1)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert len(errors) == 0
    result = cache.get("seed:thread")
    assert result is not None
    assert result.version >= 1


def test_backend_size():
    backend = _MemoryBackend()
    g1 = _make_graph("k1")
    g2 = _make_graph("k2")
    backend.put("k1", g1, ttl_seconds=60)
    backend.put("k2", g2, ttl_seconds=60)
    assert backend.size() == 2
    backend.delete("k1")
    assert backend.size() == 1


def test_backend_clear():
    backend = _MemoryBackend()
    backend.put("k1", _make_graph("k1"), ttl_seconds=60)
    backend.put("k2", _make_graph("k2"), ttl_seconds=60)
    backend.clear()
    assert backend.size() == 0
