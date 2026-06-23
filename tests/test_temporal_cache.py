"""Tests for app/services/temporal/cache.py"""

import time
from datetime import datetime
from unittest.mock import patch

import pytest

from app.models.temporal import TemporalAnalysis
from app.services.temporal.cache import TemporalAnalysisCache, _MemoryBackend

_NOW = datetime(2024, 1, 1)


def _analysis(seed_key: str = "email:x@x.com") -> TemporalAnalysis:
    return TemporalAnalysis(seed_key=seed_key, computed_at=_NOW)


@pytest.fixture
def cache() -> TemporalAnalysisCache:
    backend = _MemoryBackend()
    return TemporalAnalysisCache(backend)


def test_put_and_get_round_trip(cache):
    a = _analysis()
    cache.put(a)
    assert cache.get(a.seed_key) is not None
    assert cache.get(a.seed_key).seed_key == a.seed_key


def test_cache_miss_returns_none(cache):
    assert cache.get("nonexistent") is None


def test_invalidate_removes_entry(cache):
    a = _analysis()
    cache.put(a)
    cache.invalidate(a.seed_key)
    assert cache.get(a.seed_key) is None


def test_clear_removes_all(cache):
    cache.put(_analysis("k1"))
    cache.put(_analysis("k2"))
    cache.clear()
    assert cache.size() == 0


def test_size_counts_entries(cache):
    assert cache.size() == 0
    cache.put(_analysis("k1"))
    cache.put(_analysis("k2"))
    assert cache.size() == 2


def test_ttl_zero_no_store(monkeypatch):
    import app.services.temporal.constants as C
    monkeypatch.setenv("TEMPORAL_TTL_HOURS", "0")
    C.reload()
    backend = _MemoryBackend()
    c = TemporalAnalysisCache(backend)
    c.put(_analysis())
    assert c.size() == 0
    monkeypatch.delenv("TEMPORAL_TTL_HOURS", raising=False)
    C.reload()


def test_expired_entry_returns_none(cache):
    a = _analysis()
    # store with 1-second TTL, then fake time past expiry
    cache._backend.put(a.seed_key, a, ttl_seconds=1)
    with patch("app.services.temporal.cache.time.time", return_value=time.time() + 10):
        assert cache.get(a.seed_key) is None
