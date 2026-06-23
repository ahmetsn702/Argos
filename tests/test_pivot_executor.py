"""Tests for app/services/pivot/executor.py"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from app.models.confidence import (
    ConfidenceFinding,
    FindingType,
    SourceKind,
    SourceObservation,
)
from app.services.pivot.executor import execute_strategies


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _finding(id: str, score: float = 0.8, ftype=FindingType.EMAIL) -> ConfidenceFinding:
    now = datetime(2024, 1, 1)
    return ConfidenceFinding(
        id=id, type=ftype, value=f"{id}@test.com", raw_value=f"{id}@test.com",
        sources=[SourceObservation(
            source_id="test", source_kind=SourceKind.SCRAPING,
            weight=score, observed_at=now,
        )],
        confidence_score=score, first_seen=now, last_seen=now,
    )


def test_returns_findings_from_strategies():
    f1, f2 = _finding("a", 0.9), _finding("b", 0.7)
    s1, s2 = AsyncMock(return_value=[f1]), AsyncMock(return_value=[f2])
    result = _run(execute_strategies(FindingType.EMAIL, "x@y.com", 0.5, [s1, s2]))
    assert len(result) == 2


def test_filters_below_min_confidence():
    f1, f2 = _finding("a", 0.3), _finding("b", 0.8)
    s1 = AsyncMock(return_value=[f1, f2])
    result = _run(execute_strategies(FindingType.EMAIL, "x@y.com", 0.5, [s1]))
    assert len(result) == 1
    assert result[0].id == "b"


def test_deduplicates_by_id():
    f1, f2 = _finding("dup", 0.9), _finding("dup", 0.8)
    s1, s2 = AsyncMock(return_value=[f1]), AsyncMock(return_value=[f2])
    result = _run(execute_strategies(FindingType.EMAIL, "x@y.com", 0.5, [s1, s2]))
    assert len(result) == 1


def test_handles_strategy_exception():
    f1 = _finding("ok", 0.9)
    s_ok = AsyncMock(return_value=[f1])
    s_fail = AsyncMock(side_effect=RuntimeError("boom"))
    result = _run(execute_strategies(FindingType.EMAIL, "x@y.com", 0.5, [s_fail, s_ok]))
    assert len(result) == 1
    assert result[0].id == "ok"


def test_empty_strategies_returns_empty():
    result = _run(execute_strategies(FindingType.EMAIL, "x@y.com", 0.5, []))
    assert result == []


def test_uses_strategy_map_when_none():
    with patch("app.services.pivot.executor.strategies_for", return_value=[]) as mock_sf:
        result = _run(execute_strategies(FindingType.DOMAIN, "example.com", 0.5))
        mock_sf.assert_called_once_with(FindingType.DOMAIN)
        assert result == []
