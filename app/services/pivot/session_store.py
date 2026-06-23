# app/services/pivot/session_store.py
"""Thread-safe in-memory pivot session store.

Follows the same pattern as app/services/confidence/cache._MemoryBackend.
Stores up to 100 sessions (oldest evicted); history() returns last 20.
"""

import threading
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.models.pivot import PivotNode, PivotSession, PivotStatus

_MAX_STORE = 100


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class _MemorySessionStore:
    def __init__(self):
        self._store: Dict[str, PivotSession] = {}
        self._order: List[str] = []  # insertion order for eviction
        self._lock = threading.Lock()

    def create(
        self,
        seed_finding_id: str,
        seed_key: str,
        max_depth: int = 2,
    ) -> PivotSession:
        session = PivotSession(
            session_id=uuid.uuid4().hex,
            seed_finding_id=seed_finding_id,
            seed_key=seed_key,
            status=PivotStatus.PENDING,
            max_depth=max_depth,
            started_at=_now(),
        )
        with self._lock:
            if len(self._store) >= _MAX_STORE:
                oldest = self._order.pop(0)
                self._store.pop(oldest, None)
            self._store[session.session_id] = session
            self._order.append(session.session_id)
        return session

    def get(self, session_id: str) -> Optional[PivotSession]:
        with self._lock:
            return self._store.get(session_id)

    def update_status(self, session_id: str, status: PivotStatus, **fields) -> None:
        with self._lock:
            s = self._store.get(session_id)
            if s is None:
                return
            self._store[session_id] = s.model_copy(update={"status": status, **fields})

    def add_node(self, session_id: str, node: PivotNode) -> None:
        with self._lock:
            s = self._store.get(session_id)
            if s is None:
                return
            new_nodes = list(s.nodes_discovered) + [node]
            self._store[session_id] = s.model_copy(
                update={"nodes_discovered": new_nodes}
            )

    def mark_completed(
        self, session_id: str, took_ms: int, edges_created: int = 0
    ) -> None:
        now = _now()
        self.update_status(
            session_id,
            PivotStatus.COMPLETED,
            completed_at=now,
            took_ms=took_ms,
            edges_created=edges_created,
        )

    def mark_failed(self, session_id: str, error: str) -> None:
        now = _now()
        self.update_status(
            session_id,
            PivotStatus.FAILED,
            completed_at=now,
            error=error,
        )

    def mark_timeout(self, session_id: str, partial_took_ms: int) -> None:
        now = _now()
        self.update_status(
            session_id,
            PivotStatus.TIMEOUT,
            completed_at=now,
            took_ms=partial_took_ms,
        )

    def history(self, limit: int = 20) -> List[PivotSession]:
        with self._lock:
            sessions = [self._store[sid] for sid in self._order if sid in self._store]
        sessions.sort(key=lambda s: s.started_at, reverse=True)
        return sessions[:limit]

    def size(self) -> int:
        with self._lock:
            return len(self._store)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()
            self._order.clear()


default_session_store = _MemorySessionStore()
