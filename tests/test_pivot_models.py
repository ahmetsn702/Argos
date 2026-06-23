# tests/test_pivot_models.py
"""Tests for app/models/pivot.py and app/services/pivot/adapters.py."""

from datetime import datetime

import pytest
from pydantic import ValidationError

from app.models.confidence import FindingType
from app.models.identity import Entity, EntityType
from app.models.pivot import (
    PivotNode,
    PivotRunRequest,
    PivotSession,
    PivotStatus,
    PivotStrategy,
)
from app.services.pivot.adapters import entity_to_finding


# ── Enum ──────────────────────────────────────────────────────────────────────

def test_pivot_status_enum_values():
    assert PivotStatus.PENDING.value == "pending"
    assert PivotStatus.RUNNING.value == "running"
    assert PivotStatus.COMPLETED.value == "completed"
    assert PivotStatus.FAILED.value == "failed"
    assert PivotStatus.TIMEOUT.value == "timeout"


def test_pivot_strategy_enum_covers_seven_types():
    expected = {"email", "phone", "username", "domain", "ip", "face", "name"}
    assert {s.value for s in PivotStrategy} == expected


# ── PivotRunRequest validation ───────────────────────────────────────────────

def test_pivot_run_request_valid():
    req = PivotRunRequest(
        seed_finding_id="email:a@x.com",
        seed_key="email:a@x.com",
        max_depth=2,
        min_confidence=0.6,
    )
    assert req.dry_run is False
    assert req.strategies is None


def test_pivot_run_request_max_depth_invalid():
    with pytest.raises(ValidationError):
        PivotRunRequest(
            seed_finding_id="x",
            seed_key="x",
            max_depth=5,  # > 4
        )


def test_pivot_run_request_min_confidence_invalid():
    with pytest.raises(ValidationError):
        PivotRunRequest(
            seed_finding_id="x",
            seed_key="x",
            min_confidence=1.5,  # > 1.0
        )


# ── PivotNode + PivotSession ─────────────────────────────────────────────────

def test_pivot_node_creation():
    now = datetime(2024, 1, 1, 12, 0, 0)
    node = PivotNode(
        finding_id="email:a@x.com",
        finding_type="email",
        value="a@x.com",
        depth=1,
        confidence=0.9,
        discovered_at=now,
        modules_called=["mosint"],
    )
    assert node.parent_id is None
    assert node.modules_called == ["mosint"]


def test_pivot_session_defaults():
    s = PivotSession(
        session_id="s1",
        seed_finding_id="email:a@x.com",
        seed_key="email:a@x.com",
        max_depth=2,
        started_at=datetime(2024, 1, 1),
    )
    assert s.status == PivotStatus.PENDING
    assert s.nodes_discovered == []
    assert s.edges_created == 0
    assert s.completed_at is None


# ── adapters.entity_to_finding ───────────────────────────────────────────────

def test_entity_to_finding_email():
    ent = Entity(type=EntityType.EMAIL, value="A@X.com")
    f = entity_to_finding(ent)
    assert f is not None
    assert f.type == FindingType.EMAIL
    # Email normalisation lower-cases the value.
    assert f.value == "a@x.com"
    assert f.id == "email:a@x.com"
    assert len(f.sources) == 1


def test_entity_to_finding_breach_returns_none():
    ent = Entity(type=EntityType.BREACH, value="Adobe")
    assert entity_to_finding(ent) is None


def test_entity_to_finding_profile_to_username():
    ent = Entity(
        type=EntityType.PROFILE,
        value="ahmet",
        metadata={"platform": "instagram"},
    )
    f = entity_to_finding(ent)
    assert f is not None
    assert f.type == FindingType.USERNAME
    assert f.metadata.get("platform") == "instagram"
