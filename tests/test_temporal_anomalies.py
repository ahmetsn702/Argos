"""Tests for app/services/temporal/anomalies.py"""

from datetime import datetime, timedelta

import pytest

from app.models.temporal import AnomalySeverity, AnomalyType, TimelineEvent, TimelineEventType
from app.services.temporal.anomalies import (
    detect_all,
    detect_breach_activity_overlap,
    detect_coordinated_creation,
    detect_night_activity,
    detect_silence_then_burst,
)

_BASE = datetime(2024, 1, 1, 0, 0, 0)  # midnight UTC = 03:00 local (offset=3)


def _ev(event_type: TimelineEventType, ts: datetime, idx: int = 0,
        platform: str = None, breach_name: str = None) -> TimelineEvent:
    meta = {}
    if platform:
        meta["platform"] = platform
    if breach_name:
        meta["breach_name"] = breach_name
    return TimelineEvent(
        event_id=f"ev::{event_type.value}::{idx}",
        finding_id="fid",
        event_type=event_type,
        timestamp=ts,
        confidence=0.8,
        source="test",
        metadata=meta,
    )


# ---------------------------------------------------------------------------
# Night activity
# ---------------------------------------------------------------------------

def test_night_activity_detected_low():
    # UTC 21:00 + offset=3 → local 00:00 (night)
    night_ts = datetime(2024, 1, 1, 21, 0, 0)
    events = [_ev(TimelineEventType.FIRST_OBSERVED, night_ts, i) for i in range(2)]
    flags = detect_night_activity(events)
    assert len(flags) == 1
    assert flags[0].type == AnomalyType.NIGHT_ACTIVITY
    assert flags[0].severity == AnomalySeverity.LOW


def test_night_activity_high_severity():
    night_ts = datetime(2024, 1, 1, 21, 0, 0)
    events = [_ev(TimelineEventType.FIRST_OBSERVED, night_ts + timedelta(minutes=i), i)
              for i in range(10)]
    flags = detect_night_activity(events)
    assert flags[0].severity == AnomalySeverity.HIGH


def test_daytime_events_no_night_flag():
    # UTC 09:00 + offset=3 → local 12:00 (day)
    day_ts = datetime(2024, 1, 1, 9, 0, 0)
    events = [_ev(TimelineEventType.FIRST_OBSERVED, day_ts, i) for i in range(5)]
    assert detect_night_activity(events) == []


# ---------------------------------------------------------------------------
# Coordinated creation
# ---------------------------------------------------------------------------

def test_coordinated_creation_low():
    day = datetime(2024, 3, 15, 10, 0, 0)
    events = [
        _ev(TimelineEventType.SOCIAL_ACTIVITY, day, 0, platform="twitter"),
        _ev(TimelineEventType.SOCIAL_ACTIVITY, day, 1, platform="instagram"),
        _ev(TimelineEventType.SOCIAL_ACTIVITY, day, 2, platform="github"),
    ]
    flags = detect_coordinated_creation(events)
    assert len(flags) == 1
    assert flags[0].type == AnomalyType.COORDINATED_CREATION
    assert flags[0].severity == AnomalySeverity.LOW


def test_coordinated_creation_below_threshold_no_flag():
    day = datetime(2024, 3, 15, 10, 0, 0)
    events = [
        _ev(TimelineEventType.SOCIAL_ACTIVITY, day, 0, platform="twitter"),
        _ev(TimelineEventType.SOCIAL_ACTIVITY, day, 1, platform="instagram"),
    ]
    assert detect_coordinated_creation(events) == []


def test_coordinated_creation_high_severity():
    day = datetime(2024, 3, 15, 10, 0, 0)
    platforms = ["twitter", "instagram", "github", "linkedin",
                 "reddit", "facebook", "tiktok", "youtube"]
    events = [_ev(TimelineEventType.SOCIAL_ACTIVITY, day, i, platform=p)
              for i, p in enumerate(platforms)]
    flags = detect_coordinated_creation(events)
    assert flags[0].severity == AnomalySeverity.HIGH


# ---------------------------------------------------------------------------
# Silence then burst
# ---------------------------------------------------------------------------

def test_silence_then_burst_detected():
    t0 = datetime(2020, 1, 1)
    t1 = t0 + timedelta(days=200)   # 200-day silence
    events = [_ev(TimelineEventType.FIRST_OBSERVED, t0, 0)]
    for i in range(4):
        events.append(_ev(TimelineEventType.SOCIAL_ACTIVITY,
                          t1 + timedelta(days=i), i + 1))
    flags = detect_silence_then_burst(events)
    assert len(flags) == 1
    assert flags[0].type == AnomalyType.SILENCE_THEN_BURST


def test_silence_no_burst_no_flag():
    t0 = datetime(2020, 1, 1)
    t1 = t0 + timedelta(days=200)
    # only 1 event after the gap (< 3)
    events = [
        _ev(TimelineEventType.FIRST_OBSERVED, t0, 0),
        _ev(TimelineEventType.SOCIAL_ACTIVITY, t1, 1),
    ]
    assert detect_silence_then_burst(events) == []


# ---------------------------------------------------------------------------
# Breach activity overlap
# ---------------------------------------------------------------------------

def test_breach_activity_overlap_medium():
    breach_ts = datetime(2021, 6, 1)
    breach_ev = _ev(TimelineEventType.BREACH, breach_ts, 0, breach_name="SiteX")
    # 5 non-breach events within ±30 days
    nearby = [
        _ev(TimelineEventType.FIRST_OBSERVED, breach_ts + timedelta(days=i), i + 1)
        for i in range(5)
    ]
    flags = detect_breach_activity_overlap([breach_ev] + nearby)
    assert len(flags) == 1
    assert flags[0].severity == AnomalySeverity.MEDIUM


def test_breach_no_overlap_no_flag():
    breach_ts = datetime(2021, 6, 1)
    breach_ev = _ev(TimelineEventType.BREACH, breach_ts, 0)
    # only 1 nearby event (< 2)
    nearby = [_ev(TimelineEventType.FIRST_OBSERVED, breach_ts + timedelta(days=1), 1)]
    assert detect_breach_activity_overlap([breach_ev] + nearby) == []


# ---------------------------------------------------------------------------
# detect_all + ENV override
# ---------------------------------------------------------------------------

def test_detect_all_returns_multi_flags():
    night_ts = datetime(2024, 1, 1, 21, 0, 0)
    night_events = [_ev(TimelineEventType.FIRST_OBSERVED, night_ts, i) for i in range(2)]
    breach_ts = datetime(2021, 6, 1)
    breach_ev = _ev(TimelineEventType.BREACH, breach_ts, 10, breach_name="X")
    nearby = [_ev(TimelineEventType.FIRST_OBSERVED, breach_ts + timedelta(days=i), 20 + i)
              for i in range(5)]
    flags = detect_all(night_events + [breach_ev] + nearby)
    types = {f.type for f in flags}
    assert AnomalyType.NIGHT_ACTIVITY in types
    assert AnomalyType.BREACH_ACTIVITY_OVERLAP in types


def test_env_override_burst_min_platforms(monkeypatch):
    import app.services.temporal.constants as C
    monkeypatch.setenv("TEMPORAL_BURST_MIN_PLATFORMS", "2")
    C.reload()
    day = datetime(2024, 3, 15, 10, 0, 0)
    events = [
        _ev(TimelineEventType.SOCIAL_ACTIVITY, day, 0, platform="twitter"),
        _ev(TimelineEventType.SOCIAL_ACTIVITY, day, 1, platform="instagram"),
    ]
    flags = detect_coordinated_creation(events)
    assert len(flags) == 1
    monkeypatch.delenv("TEMPORAL_BURST_MIN_PLATFORMS", raising=False)
    C.reload()
