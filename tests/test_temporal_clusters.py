"""Tests for app/services/temporal/clusters.py"""

from datetime import datetime, timedelta

from app.models.temporal import TimelineEvent, TimelineEventType
from app.services.temporal.clusters import detect_clusters

_BASE = datetime(2020, 1, 1, 0, 0, 0)


def _ev(minutes_offset: int, idx: int = 0) -> TimelineEvent:
    ts = _BASE + timedelta(minutes=minutes_offset)
    return TimelineEvent(
        event_id=f"ev::{idx}::{minutes_offset}",
        finding_id="fid",
        event_type=TimelineEventType.BREACH,
        timestamp=ts,
        confidence=0.8,
        source="hibp",
    )


# --- basic cases ---

def test_empty_events_returns_empty():
    assert detect_clusters([]) == []


def test_single_event_returns_empty():
    assert detect_clusters([_ev(0)]) == []


def test_two_events_within_window_form_cluster():
    events = [_ev(0, 0), _ev(30, 1)]  # 30 min apart, default window=60
    clusters = detect_clusters(events, window_minutes=60)
    assert len(clusters) == 1
    assert clusters[0].span_minutes == 30
    assert len(clusters[0].event_ids) == 2


def test_two_events_outside_window_no_cluster():
    events = [_ev(0, 0), _ev(200, 1)]  # 200 min > 60
    clusters = detect_clusters(events, window_minutes=60)
    assert clusters == []


# --- three events ---

def test_three_events_within_window_one_cluster():
    events = [_ev(0, 0), _ev(30, 1), _ev(60, 2)]  # each 30 min apart
    clusters = detect_clusters(events, window_minutes=60)
    assert len(clusters) == 1
    assert len(clusters[0].event_ids) == 3


def test_three_events_split_into_two_clusters():
    # first two close, third far away
    events = [_ev(0, 0), _ev(30, 1), _ev(500, 2), _ev(530, 3)]
    clusters = detect_clusters(events, window_minutes=60)
    assert len(clusters) == 2
    assert len(clusters[0].event_ids) == 2
    assert len(clusters[1].event_ids) == 2


def test_span_minutes_computed_correctly():
    events = [_ev(0, 0), _ev(45, 1)]
    clusters = detect_clusters(events, window_minutes=60)
    assert clusters[0].span_minutes == 45


# --- ENV override ---

def test_env_override_window(monkeypatch):
    import app.services.temporal.constants as C
    monkeypatch.setenv("TEMPORAL_CLUSTER_WINDOW_MIN", "10")
    C.reload()
    # 30-min gap exceeds 10-min window → no cluster
    events = [_ev(0, 0), _ev(30, 1)]
    clusters = detect_clusters(events)  # uses ENV default
    assert clusters == []
    monkeypatch.delenv("TEMPORAL_CLUSTER_WINDOW_MIN", raising=False)
    C.reload()
