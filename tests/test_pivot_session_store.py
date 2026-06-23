# tests/test_pivot_session_store.py
"""Tests for app/services/pivot/session_store.py"""

import threading
from datetime import datetime

from app.models.pivot import PivotNode, PivotStatus
from app.services.pivot.session_store import _MemorySessionStore


def _store() -> _MemorySessionStore:
    return _MemorySessionStore()


def _node(depth=1) -> PivotNode:
    return PivotNode(
        finding_id="email:a@x.com",
        finding_type="email",
        value="a@x.com",
        depth=depth,
        confidence=0.8,
        discovered_at=datetime(2024, 1, 1),
    )


# ── create / get ──────────────────────────────────────────────────────────────

def test_create_and_get_roundtrip():
    store = _store()
    s = store.create("email:a@x.com", "email:a@x.com", max_depth=2)
    got = store.get(s.session_id)
    assert got is not None
    assert got.session_id == s.session_id
    assert got.status == PivotStatus.PENDING


def test_get_nonexistent_returns_none():
    store = _store()
    assert store.get("does_not_exist") is None


# ── update_status ─────────────────────────────────────────────────────────────

def test_update_status_changes_status():
    store = _store()
    s = store.create("email:a@x.com", "email:a@x.com")
    store.update_status(s.session_id, PivotStatus.RUNNING)
    assert store.get(s.session_id).status == PivotStatus.RUNNING


def test_update_status_missing_session_is_noop():
    store = _store()
    store.update_status("ghost", PivotStatus.RUNNING)  # must not raise


# ── mark_completed ────────────────────────────────────────────────────────────

def test_mark_completed_sets_fields():
    store = _store()
    s = store.create("email:a@x.com", "email:a@x.com")
    store.mark_completed(s.session_id, took_ms=123, edges_created=5)
    got = store.get(s.session_id)
    assert got.status == PivotStatus.COMPLETED
    assert got.took_ms == 123
    assert got.edges_created == 5
    assert got.completed_at is not None


def test_mark_failed_sets_error():
    store = _store()
    s = store.create("email:a@x.com", "email:a@x.com")
    store.mark_failed(s.session_id, "boom")
    got = store.get(s.session_id)
    assert got.status == PivotStatus.FAILED
    assert got.error == "boom"


def test_mark_timeout_sets_status():
    store = _store()
    s = store.create("email:a@x.com", "email:a@x.com")
    store.mark_timeout(s.session_id, partial_took_ms=9999)
    got = store.get(s.session_id)
    assert got.status == PivotStatus.TIMEOUT
    assert got.took_ms == 9999


# ── add_node ──────────────────────────────────────────────────────────────────

def test_add_node_appends():
    store = _store()
    s = store.create("email:a@x.com", "email:a@x.com")
    store.add_node(s.session_id, _node())
    store.add_node(s.session_id, _node(depth=2))
    got = store.get(s.session_id)
    assert len(got.nodes_discovered) == 2


# ── history ───────────────────────────────────────────────────────────────────

def test_history_returns_sorted_desc_limited():
    store = _store()
    ids = []
    for _ in range(5):
        s = store.create("email:a@x.com", "email:a@x.com")
        ids.append(s.session_id)
    hist = store.history(limit=3)
    assert len(hist) == 3
    # sorted descending by started_at (all same instant → stable by insertion desc)
    assert all(
        hist[i].started_at >= hist[i + 1].started_at for i in range(len(hist) - 1)
    )


def test_history_default_limit_20():
    store = _store()
    for _ in range(25):
        store.create("email:a@x.com", "email:a@x.com")
    assert len(store.history()) == 20


# ── eviction at _MAX_STORE=100 ────────────────────────────────────────────────

def test_eviction_keeps_store_bounded():
    store = _store()
    ids = []
    for _ in range(105):
        s = store.create("email:a@x.com", "email:a@x.com")
        ids.append(s.session_id)
    assert store.size() == 100
    # Oldest should be evicted
    assert store.get(ids[0]) is None
    assert store.get(ids[-1]) is not None


# ── thread safety ─────────────────────────────────────────────────────────────

def test_thread_safety_concurrent_create():
    store = _store()
    errors = []

    def _worker():
        try:
            s = store.create("email:a@x.com", "email:a@x.com")
            store.mark_completed(s.session_id, took_ms=1)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=_worker) for _ in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == []
    assert store.size() == 10
