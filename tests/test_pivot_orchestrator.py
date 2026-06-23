"""Tests for app/services/pivot/orchestrator.py"""

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
from app.models.pivot import PivotRunRequest, PivotStatus, PivotStrategy
from app.services.pivot.orchestrator import run_pivot_session
from app.services.pivot.session_store import default_session_store


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _finding(id: str, ftype=FindingType.USERNAME, value="user1") -> ConfidenceFinding:
    now = datetime(2024, 1, 1)
    return ConfidenceFinding(
        id=id, type=ftype, value=value, raw_value=value,
        sources=[SourceObservation(
            source_id="t", source_kind=SourceKind.SCRAPING,
            weight=0.8, observed_at=now,
        )],
        confidence_score=0.8, first_seen=now, last_seen=now,
    )


@pytest.fixture(autouse=True)
def _clear_store():
    default_session_store.clear()
    yield
    default_session_store.clear()


def test_dry_run_returns_plan_only():
    req = PivotRunRequest(
        seed_finding_id="email:a@x.com", seed_key="a@x.com",
        max_depth=2, dry_run=True,
    )
    session = _run(run_pivot_session(req))
    assert session.status == PivotStatus.COMPLETED
    assert session.nodes_discovered == []
    assert session.plan is not None
    assert session.took_ms == 0


@patch("app.services.pivot.orchestrator.execute_strategies")
def test_bfs_discovers_nodes(mock_exec):
    f1 = _finding("u:user1", FindingType.USERNAME, "user1")
    mock_exec.return_value = [f1]
    req = PivotRunRequest(
        seed_finding_id="email:a@x.com", seed_key="a@x.com",
        max_depth=1, min_confidence=0.5,
    )
    session = _run(run_pivot_session(req))
    assert session.status == PivotStatus.COMPLETED
    assert len(session.nodes_discovered) == 1
    assert session.nodes_discovered[0].finding_id == "u:user1"


@patch("app.services.pivot.orchestrator.execute_strategies")
def test_respects_max_depth(mock_exec):
    f1 = _finding("d1", FindingType.DOMAIN, "x.com")
    f2 = _finding("d2", FindingType.DOMAIN, "y.com")
    mock_exec.side_effect = [[f1], [f2], []]
    req = PivotRunRequest(
        seed_finding_id="email:a@x.com", seed_key="a@x.com",
        max_depth=2, min_confidence=0.5,
    )
    session = _run(run_pivot_session(req))
    assert session.status == PivotStatus.COMPLETED
    assert len(session.nodes_discovered) == 2


@patch("app.services.pivot.orchestrator.execute_strategies")
def test_handles_executor_exception(mock_exec):
    mock_exec.side_effect = RuntimeError("expander crash")
    req = PivotRunRequest(
        seed_finding_id="email:a@x.com", seed_key="a@x.com",
        max_depth=1,
    )
    session = _run(run_pivot_session(req))
    assert session.status == PivotStatus.FAILED
    assert "expander crash" in session.error


@patch("app.services.pivot.orchestrator.execute_strategies")
def test_timeout_marks_session(mock_exec):
    async def slow(*a, **kw):
        await asyncio.sleep(0.1)
        return []
    mock_exec.side_effect = slow
    with patch("app.services.pivot.orchestrator._TIMEOUT_SECONDS", -1):
        req = PivotRunRequest(
            seed_finding_id="email:a@x.com", seed_key="a@x.com",
            max_depth=2,
        )
        session = _run(run_pivot_session(req))
    assert session.status == PivotStatus.TIMEOUT


@patch("app.services.pivot.orchestrator.execute_strategies")
def test_strategy_filter_limits_ftypes(mock_exec):
    f1 = _finding("u:user1", FindingType.USERNAME, "user1")
    mock_exec.return_value = [f1]
    req = PivotRunRequest(
        seed_finding_id="email:a@x.com", seed_key="a@x.com",
        max_depth=1, strategies=[PivotStrategy.EMAIL],
    )
    session = _run(run_pivot_session(req))
    assert session.status == PivotStatus.COMPLETED
    mock_exec.assert_called()


def test_session_stored_in_store():
    req = PivotRunRequest(
        seed_finding_id="email:a@x.com", seed_key="a@x.com",
        max_depth=1, dry_run=True,
    )
    session = _run(run_pivot_session(req))
    stored = default_session_store.get(session.session_id)
    assert stored is not None
    assert stored.session_id == session.session_id


@patch("app.services.pivot.orchestrator.execute_strategies")
def test_deduplicates_across_depths(mock_exec):
    f1 = _finding("same", FindingType.DOMAIN, "x.com")
    mock_exec.return_value = [f1]
    req = PivotRunRequest(
        seed_finding_id="email:a@x.com", seed_key="a@x.com",
        max_depth=2, min_confidence=0.5,
    )
    session = _run(run_pivot_session(req))
    assert session.status == PivotStatus.COMPLETED
    assert len(session.nodes_discovered) == 1
