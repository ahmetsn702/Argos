# app/core/cache.py
"""Production-ready cache layer: Redis (preferred) → in-memory TTLCache fallback."""

import json
import logging
from typing import Any, Optional

from cachetools import TTLCache

try:
    import redis.asyncio as aioredis
    REDIS_AVAILABLE = True
except ImportError:
    REDIS_AVAILABLE = False

logger = logging.getLogger(__name__)


class CacheManager:
    def __init__(self, redis_url: Optional[str] = None, default_ttl: int = 300):
        self.default_ttl = default_ttl
        self._memory: TTLCache = TTLCache(maxsize=1000, ttl=default_ttl)
        self._redis = None
        if redis_url and REDIS_AVAILABLE:
            try:
                self._redis = aioredis.from_url(redis_url, decode_responses=True)
            except Exception:
                logger.warning("Redis connection failed, using memory cache.")

    async def get(self, key: str) -> Optional[Any]:
        if self._redis:
            try:
                raw = await self._redis.get(key)
                return json.loads(raw) if raw is not None else None
            except Exception:
                pass
        raw = self._memory.get(key)
        return raw

    async def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        ttl = ttl or self.default_ttl
        if self._redis:
            try:
                await self._redis.setex(key, ttl, json.dumps(value))
                return
            except Exception:
                pass
        self._memory[key] = value

    async def delete(self, key: str) -> None:
        if self._redis:
            try:
                await self._redis.delete(key)
            except Exception:
                pass
        self._memory.pop(key, None)

    async def exists(self, key: str) -> bool:
        return await self.get(key) is not None


_instance: Optional[CacheManager] = None


def get_cache() -> CacheManager:
    global _instance
    if _instance is None:
        from app.core.config import settings
        _instance = CacheManager(
            redis_url=settings.REDIS_URL,
            default_ttl=settings.CACHE_TTL,
        )
    return _instance
