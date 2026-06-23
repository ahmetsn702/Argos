"""Tests for app/services/temporal/service.py"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.models.confidence import ConfidenceGraph
from app.models.temporal import AnomalyFlag, AnomalySeverity, AnomalyType, TemporalNarrative
from app.services.temporal.cache import _MemoryBackend, TemporalAnalysisCache
from app.services.temporal import service as svc


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mock_graph(seed_key: str = "email:x@x.com") -> ConfidenceGraph:
    return ConfidenceGraph(
        seed_key=seed_key, findings={}, edges=[],
        computed_at=datetime(2024, 1, 1), version=1,
    )


def _mock_flag() -> AnomalyFlag:
    return AnomalyFlag(
        anomaly_id="a1", type=AnomalyType.NIGHT_ACTIVITY,
        severity=AnomalySeverity.LOW,
        event_ids=["ev1"], explanation="Gece.",
    )


@pytest.fixture(autouse=True)
def reset_cache():
    from app.services.temporal.cache import _default_backend
    _default_backend.clear()
    yield
    _default_backend.clear()


# --- no confidence graph ---

def test_analyze_returns_none_when_no_graph():
    with patch("app.services.temporal.service.default_cache") as mock_cc:
        mock_cc.get.return_value = None
        result = _run(svc.analyze("email:x@x.com"))
    assert result is None


# --- basic analysis ---

def test_analyze_returns_temporal_analysis():
    graph = _mock_graph()
    with patch("app.services.temporal.service.default_cache") as mock_cc:
        mock_cc.get.return_value = graph
        result = _run(svc.analyze("email:x@x.com"))
    assert result is not None
    assert result.seed_key == "email:x@x.com"
    assert result.narrative is None  # narrative=False default


# --- narrative not called when anomalies empty ---

def test_narrative_not_called_when_no_anomalies():
    graph = _mock_graph()
    with patch("app.services.temporal.service.default_cache") as mock_cc, \
         patch("app.services.temporal.service.detect_all", return_value=[]), \
         patch("app.services.temporal.service.TemporalNarrator") as mock_narrator:
        mock_cc.get.return_value = graph
        result = _run(svc.analyze("email:x@x.com", narrative=True))
    mock_narrator.return_value.generate.assert_not_called()
    assert result.narrative is None


# --- narrative called when anomalies present and narrative=True ---

def test_narrative_called_when_anomalies_and_requested():
    graph = _mock_graph()
    flag = _mock_flag()
    mock_narr = TemporalNarrative(
        summary="Özet.", risk_level="medium",
        key_observations=[], model="gemini-3.5-flash",
        generated_at=datetime(2024, 1, 1),
    )
    with patch("app.services.temporal.service.default_cache") as mock_cc, \
         patch("app.services.temporal.service.detect_all", return_value=[flag]), \
         patch("app.services.temporal.service.TemporalNarrator") as mock_cls:
        mock_cc.get.return_value = graph
        mock_cls.return_value.generate = AsyncMock(return_value=mock_narr)
        result = _run(svc.analyze("email:x@x.com", narrative=True))
    assert result.narrative is not None
    assert result.narrative.summary == "Özet."


# --- cache hit returns cached without re-extracting ---

def test_cache_hit_skips_extraction():
    graph = _mock_graph()
    with patch("app.services.temporal.service.default_cache") as mock_cc, \
         patch("app.services.temporal.service.extract_events") as mock_extract:
        mock_cc.get.return_value = graph
        # first call populates cache
        r1 = _run(svc.analyze("email:x@x.com"))
        # second call should hit temporal cache, not re-extract
        r2 = _run(svc.analyze("email:x@x.com"))
    assert mock_extract.call_count == 1  # only called once
    assert r1.seed_key == r2.seed_key


# --- force=True invalidates cache ---

def test_force_rebuilds_analysis():
    graph = _mock_graph()
    with patch("app.services.temporal.service.default_cache") as mock_cc, \
         patch("app.services.temporal.service.extract_events") as mock_extract:
        mock_extract.return_value = []
        mock_cc.get.return_value = graph
        _run(svc.analyze("email:x@x.com"))
        _run(svc.analyze("email:x@x.com", force=True))
    assert mock_extract.call_count == 2  # called twice due to force
