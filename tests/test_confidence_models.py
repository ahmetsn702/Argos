# tests/test_confidence_models.py
"""Tests for app/models/confidence.py"""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.confidence import (
    ConfidenceEdge,
    ConfidenceFinding,
    ConfidenceGraph,
    EdgeType,
    FindingType,
    SourceKind,
    SourceObservation,
)

_NOW = datetime(2026, 1, 1, 12, 0, 0)


def _obs(**kwargs):
    defaults = dict(source_id="mosint", source_kind=SourceKind.SCRAPING,
                    weight=0.5, observed_at=_NOW)
    defaults.update(kwargs)
    return SourceObservation(**defaults)


def _finding(**kwargs):
    defaults = dict(id="email:test@example.com", type=FindingType.EMAIL,
                    value="test@example.com", raw_value="Test@Example.com",
                    confidence_score=0.5, first_seen=_NOW, last_seen=_NOW)
    defaults.update(kwargs)
    return ConfidenceFinding(**defaults)


def test_finding_invalid_score():
    with pytest.raises(ValidationError):
        _finding(confidence_score=1.5)


def test_finding_score_negative():
    with pytest.raises(ValidationError):
        _finding(confidence_score=-0.1)


def test_finding_valid():
    f = _finding()
    assert f.id == "email:test@example.com"
    assert f.type == FindingType.EMAIL
    assert f.confidence_score == 0.5
    assert f.sources == []
    assert f.metadata == {}


def test_edge_self_loop():
    with pytest.raises(ValidationError):
        ConfidenceEdge(source_id="a", target_id="a",
                       edge_type=EdgeType.SAME_AS, weight=0.5)


def test_edge_valid():
    e = ConfidenceEdge(source_id="a", target_id="b",
                       edge_type=EdgeType.SUPPORTS, weight=0.8)
    assert e.source_id == "a"
    assert e.target_id == "b"
    assert e.edge_type == EdgeType.SUPPORTS


def test_graph_empty():
    g = ConfidenceGraph(seed_key="test_seed", computed_at=_NOW)
    assert g.findings == {}
    assert g.edges == []
    assert g.version == 1


def test_source_observation_weight_range():
    with pytest.raises(ValidationError):
        _obs(weight=1.1)


def test_source_observation_weight_zero():
    obs = _obs(weight=0.0)
    assert obs.weight == 0.0


def test_source_observation_contradicts_default():
    obs = _obs()
    assert obs.contradicts == []


def test_finding_with_sources():
    obs = _obs()
    f = _finding(sources=[obs])
    assert len(f.sources) == 1
    assert f.sources[0].source_kind == SourceKind.SCRAPING
