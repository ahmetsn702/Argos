"""TTL-aware in-memory cache for TemporalAnalysis objects.

Pattern: identical to app/services/confidence/cache._MemoryBackend.
TTL default: TEMPORAL_TTL_HOURS env var (default 6h).
TTL=0 → no-store mode.
"""

import threading
import time
from typing import Dict, Optional, Tuple

from app.models.temporal import TemporalAnalysis
from app.services.temporal import constants


class _MemoryBackend:
    def __init__(self):
        self._store: Dict[str, Tuple[float, TemporalAnalysis]] = {}
        self._lock = threading.Lock()

    def get(self, key: str) -> Optional[TemporalAnalysis]:
        with self._lock:
            item = self._store.get(key)
            if item is None:
                return None
            expires_at, analysis = item
            if expires_at != 0 and time.time() > expires_at:
                del self._store[key]
                return None
            return analysis

    def put(self, key: str, analysis: TemporalAnalysis, ttl_seconds: float) -> None:
        with self._lock:
            expires_at = 0 if ttl_seconds == 0 else time.time() + ttl_seconds
            self._store[key] = (expires_at, analysis)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def size(self) -> int:
        with self._lock:
            return len(self._store)


class TemporalAnalysisCache:
    def __init__(self, backend: _MemoryBackend = None):
        self._backend = backend or _default_backend

    def _ttl_seconds(self) -> float:
        return constants.TTL_HOURS * 3600

    def get(self, seed_key: str) -> Optional[TemporalAnalysis]:
        return self._backend.get(seed_key)

    def put(self, analysis: TemporalAnalysis) -> None:
        ttl = self._ttl_seconds()
        if ttl == 0:
            return
        self._backend.put(analysis.seed_key, analysis, ttl)

    def invalidate(self, seed_key: str) -> None:
        self._backend.delete(seed_key)

    def clear(self) -> None:
        self._backend.clear()

    def size(self) -> int:
        return self._backend.size()


_default_backend = _MemoryBackend()
default_temporal_cache = TemporalAnalysisCache(_default_backend)
