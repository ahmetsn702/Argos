"""Tests for BaseService."""

import asyncio

from app.services.base import BaseService


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def test_cache_miss():
    svc = BaseService(cache_ttl=300)
    assert _run(svc.cache_get("nonexistent")) is None


def test_cache_set_get():
    svc = BaseService(cache_ttl=300)
    _run(svc.cache_set("key1", {"data": 42}))
    assert _run(svc.cache_get("key1")) == {"data": 42}


def test_cache_expiry():
    """BaseService kendi singleton cache_manager'ını kullanır; TTL davranışı
    test_cache.py::test_cache_ttl'de doğrulanıyor. Burada sadece set/get döngüsü."""
    svc = BaseService(cache_ttl=300)
    _run(svc.cache_set("key2", "value"))
    assert _run(svc.cache_get("key2")) == "value"


def test_cache_key():
    svc = BaseService()
    k1 = svc.cache_key("user", "john")
    k2 = svc.cache_key("user", "john")
    k3 = svc.cache_key("user", "jane")
    assert k1 == k2
    assert k1 != k3
