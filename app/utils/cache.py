# -*- coding: utf-8 -*-
from cachetools import TTLCache

# 1 saatlik TTL cache (3600s)
ig_cache = TTLCache(maxsize=500, ttl=3600)
x_cache  = TTLCache(maxsize=1000, ttl=3600)
scan_cache = TTLCache(maxsize=200, ttl=3600)  # Unified scan için ayrı cache

def cache_get(cache, key):
    try:
        return cache.get(key)
    except Exception:
        return None

def cache_set(cache, key, value):
    try:
        cache[key] = value
    except Exception:
        pass
