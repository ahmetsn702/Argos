"""Tests for app/services/temporal/extractors.py"""

from datetime import datetime

from app.models.confidence import (
    ConfidenceFinding,
    ConfidenceGraph,
    FindingType,
    SourceKind,
    SourceObservation,
)
from app.models.temporal import TimelineEventType
from app.services.temporal.extractors import extract_events

_T0 = datetime(2020, 1, 1, 0, 0, 0)
_T1 = datetime(2021, 6, 15, 0, 0, 0)
_T2 = datetime(2022, 3, 10, 0, 0, 0)


def _obs(source_id="src") -> SourceObservation:
    return SourceObservation(
        source_id=source_id, source_kind=SourceKind.SCRAPING,
        weight=0.5, observed_at=_T0,
    )


def _finding(fid: str, ftype: FindingType, first_seen=_T0,
             metadata=None) -> ConfidenceFinding:
    return ConfidenceFinding(
        id=fid, type=ftype, value=fid, raw_value=fid,
        sources=[_obs()],
        confidence_score=0.7,
        first_seen=first_seen,
        last_seen=first_seen,
        metadata=metadata or {},
    )


def _graph(*findings) -> ConfidenceGraph:
    return ConfidenceGraph(
        seed_key="test",
        findings={f.id: f for f in findings},
        edges=[],
        computed_at=_T0,
    )


# --- empty graph ---

def test_empty_graph_returns_empty():
    assert extract_events(_graph()) == []


# --- FIRST_OBSERVED always produced ---

def test_first_observed_always_emitted():
    f = _finding("u:alice", FindingType.USERNAME, _T0)
    events = extract_events(_graph(f))
    types = [e.event_type for e in events]
    assert TimelineEventType.FIRST_OBSERVED in types


# --- EMAIL: breach events ---

def test_email_with_two_breaches_produces_correct_events():
    f = _finding("email:a@x.com", FindingType.EMAIL, _T0, metadata={
        "breaches": [
            {"Name": "SiteA", "BreachDate": "2021-06-15", "DataClasses": ["Email addresses"]},
            {"Name": "SiteB", "BreachDate": "2022-03-10", "DataClasses": ["Passwords"]},
        ]
    })
    events = extract_events(_graph(f))
    types = [e.event_type for e in events]
    # FIRST_OBSERVED + BREACH + BREACH + BREACH_PASSWORD = 4
    assert types.count(TimelineEventType.FIRST_OBSERVED) == 1
    assert types.count(TimelineEventType.BREACH) == 2
    assert types.count(TimelineEventType.BREACH_PASSWORD) == 1
    assert len(events) == 4


def test_breach_password_only_on_password_class():
    f = _finding("email:b@x.com", FindingType.EMAIL, _T0, metadata={
        "breaches": [
            {"Name": "NoPassSite", "BreachDate": "2021-01-01",
             "DataClasses": ["Email addresses"]},
        ]
    })
    events = extract_events(_graph(f))
    types = [e.event_type for e in events]
    assert TimelineEventType.BREACH_PASSWORD not in types
    assert TimelineEventType.BREACH in types


# --- DOMAIN ---

def test_domain_with_created_date_produces_domain_registered():
    f = _finding("domain:x.com", FindingType.DOMAIN, _T0,
                 metadata={"created_date": "2019-05-01"})
    events = extract_events(_graph(f))
    types = [e.event_type for e in events]
    assert TimelineEventType.DOMAIN_REGISTERED in types
    assert TimelineEventType.FIRST_OBSERVED in types
    assert len(events) == 2


def test_domain_invalid_date_skips_domain_registered():
    f = _finding("domain:y.com", FindingType.DOMAIN, _T0,
                 metadata={"created_date": "not-a-date"})
    events = extract_events(_graph(f))
    types = [e.event_type for e in events]
    assert TimelineEventType.DOMAIN_REGISTERED not in types
    assert TimelineEventType.FIRST_OBSERVED in types


# --- USERNAME / SOCIAL_ACTIVITY ---

def test_username_with_platform_produces_social_activity():
    f = _finding("u:bob", FindingType.USERNAME, _T0,
                 metadata={"platform": "twitter"})
    events = extract_events(_graph(f))
    types = [e.event_type for e in events]
    assert TimelineEventType.SOCIAL_ACTIVITY in types


def test_username_without_platform_no_social_activity():
    f = _finding("u:charlie", FindingType.USERNAME, _T0, metadata={})
    events = extract_events(_graph(f))
    types = [e.event_type for e in events]
    assert TimelineEventType.SOCIAL_ACTIVITY not in types


# --- sort order ---

def test_events_sorted_ascending_by_timestamp():
    f = _finding("email:c@x.com", FindingType.EMAIL, _T2, metadata={
        "breaches": [
            {"Name": "Earlier", "BreachDate": "2018-01-01", "DataClasses": []},
            {"Name": "Later", "BreachDate": "2023-01-01", "DataClasses": []},
        ]
    })
    events = extract_events(_graph(f))
    timestamps = [e.timestamp for e in events]
    assert timestamps == sorted(timestamps)
