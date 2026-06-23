"""Base service: CacheManager-backed async cache, logging."""

import hashlib
import logging
import time
from typing import Any, Optional

from app.core.cache import CacheManager, get_cache


class BaseService:
    def __init__(self, cache_ttl: int = 300):
        self.cache_ttl = cache_ttl
        self._cache: dict = {}  # kept for backward compat (subclasses may use directly)
        self.logger = logging.getLogger(self.__class__.__name__)
        self._cache_manager: CacheManager = get_cache()

    async def cache_get(self, key: str) -> Optional[Any]:
        return await self._cache_manager.get(key)

    async def cache_set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        await self._cache_manager.set(key, value, ttl or self.cache_ttl)

    def cache_key(self, *args) -> str:
        raw = ":".join(str(a) for a in args)
        return hashlib.sha1(raw.encode()).hexdigest()
