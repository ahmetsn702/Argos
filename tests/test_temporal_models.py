"""Tests for app/models/temporal.py"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.temporal import (
    AnomalyFlag,
    AnomalySeverity,
    AnomalyType,
    TemporalAnalysis,
    TemporalNarrative,
    TimelineCluster,
    TimelineEvent,
    TimelineEventType,
)

_NOW = datetime(2024, 6, 1, 12, 0, 0)


def _event(**kw) -> TimelineEvent:
    defaults = dict(
        event_id="ev1",
        finding_id="fid1",
        event_type=TimelineEventType.BREACH,
        timestamp=_NOW,
        confidence=0.8,
        source="hibp",
    )
    return TimelineEvent(**{**defaults, **kw})


def test_timeline_event_valid():
    e = _event()
    assert e.event_type == TimelineEventType.BREACH
    assert e.confidence == 0.8
    assert e.metadata == {}


def test_timeline_event_confidence_bounds():
    with pytest.raises(ValidationError):
        _event(confidence=1.1)
    with pytest.raises(ValidationError):
        _event(confidence=-0.1)


def test_timeline_event_invalid_event_type():
    with pytest.raises(ValidationError):
        _event(event_type="nonexistent_type")


def test_anomaly_flag_valid():
    flag = AnomalyFlag(
        anomaly_id="a1",
        type=AnomalyType.NIGHT_ACTIVITY,
        severity=AnomalySeverity.LOW,
        event_ids=["ev1", "ev2"],
        explanation="Gece aktivitesi tespit edildi.",
    )
    assert flag.severity == AnomalySeverity.LOW
    assert flag.metadata == {}


def test_anomaly_flag_invalid_severity():
    with pytest.raises(ValidationError):
        AnomalyFlag(
            anomaly_id="a1",
            type=AnomalyType.NIGHT_ACTIVITY,
            severity="extreme",
            event_ids=[],
            explanation="x",
        )


def test_temporal_analysis_narrative_default_none():
    analysis = TemporalAnalysis(seed_key="email:x@x.com", computed_at=_NOW)
    assert analysis.narrative is None
    assert analysis.events == []
    assert analysis.anomalies == []
    assert analysis.clusters == []


def test_temporal_analysis_model_dump_round_trip():
    analysis = TemporalAnalysis(seed_key="email:x@x.com", computed_at=_NOW)
    dumped = analysis.model_dump()
    restored = TemporalAnalysis(**dumped)
    assert restored.seed_key == analysis.seed_key
    assert restored.narrative is None
