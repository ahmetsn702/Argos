# tests/test_cache.py
"""CacheManager unit testleri — memory fallback (Redis yok)."""
import asyncio
import time

import pytest

from app.core.cache import CacheManager


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mgr(ttl=300) -> CacheManager:
    """Redis olmadan (memory-only) CacheManager."""
    return CacheManager(redis_url=None, default_ttl=ttl)


def test_cache_set_get():
    """set → get aynı değeri döndürür."""
    m = _mgr()
    _run(m.set("k1", {"x": 1}))
    assert _run(m.get("k1")) == {"x": 1}


def test_cache_miss():
    """Olmayan key → None döner."""
    m = _mgr()
    assert _run(m.get("nonexistent")) is None


def test_cache_ttl():
    """ttl=1 ile set → 1.1s sonra None döner."""
    m = _mgr(ttl=1)
    _run(m.set("k_ttl", "value", ttl=1))
    assert _run(m.get("k_ttl")) == "value"
    time.sleep(1.1)
    assert _run(m.get("k_ttl")) is None


def test_cache_delete():
    """set → delete → None döner."""
    m = _mgr()
    _run(m.set("k_del", 42))
    assert _run(m.get("k_del")) == 42
    _run(m.delete("k_del"))
    assert _run(m.get("k_del")) is None


def test_cache_memory_fallback():
    """REDIS_URL=None ile CacheManager → memory cache çalışır."""
    m = CacheManager(redis_url=None, default_ttl=60)
    assert m._redis is None
    _run(m.set("fb", [1, 2, 3]))
    assert _run(m.get("fb")) == [1, 2, 3]
    assert _run(m.exists("fb")) is True
    assert _run(m.exists("missing")) is False
