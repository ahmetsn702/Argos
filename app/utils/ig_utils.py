from __future__ import annotations
import time, random, requests, html
from typing import Any, Optional, Tuple

# basit bellek cache (TTL saniye)
_CACHE: dict[Any, Tuple[float, Any]] = {}

def cache_get(key: Any) -> Optional[Any]:
    rec = _CACHE.get(key)
    if not rec: return None
    exp, val = rec
    if exp < time.time():
        _CACHE.pop(key, None)
        return None
    return val

def cache_put(key: Any, val: Any, ttl: int = 600) -> None:
    _CACHE[key] = (time.time() + ttl, val)

def get_retry(url: str, *, tries: int = 2, delay: float = 0.4, backoff: float = 1.7, **kwargs) -> requests.Response:
    last_exc = None
    for i in range(tries):
        try:
            return requests.get(url, **kwargs)
        except Exception as e:
            last_exc = e
            time.sleep(delay)
            delay *= backoff
    raise last_exc

def sanitize_title(title: str, username: str) -> str:
    if not title:
        return f"Instagram (@{username}) • Instagram photos and videos"
    tl = title.strip().lower()
    if tl.startswith("login"):
        return f"Instagram (@{username}) • Instagram photos and videos"
    return title