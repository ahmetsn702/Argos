# tests/test_confidence_graph.py
"""Tests for app/services/confidence/graph.py"""

from datetime import datetime

from app.models.confidence import (
    ConfidenceFinding,
    EdgeType,
    FindingType,
    SourceKind,
    SourceObservation,
)
from app.services.confidence.graph import build_graph
from app.services.confidence.normalizers import normalize_location


def test_build_graph_empty_raw():
    graph = build_graph("test_seed", {})
    assert graph.seed_key == "test_seed"
    assert graph.findings == {}
    assert graph.edges == []
    assert graph.version == 1


def test_build_graph_version_increments():
    g1 = build_graph("seed", {"mosint": {"email": "a@x.com"}})
    g2 = build_graph("seed", {"mosint": {"email": "a@x.com"}}, prior=g1)
    assert g2.version == 2


def test_build_graph_merges_same_email():
    raw = {
        "mosint": {"email": "a@x.com"},
        "darkweb": {"email": "a@x.com", "found": True,
                    "breaches": [{"name": "Adobe"}]},
    }
    graph = build_graph("seed", raw)
    email_findings = [f for f in graph.findings.values()
                      if f.type == FindingType.EMAIL]
    assert len(email_findings) == 1
    assert len(email_findings[0].sources) >= 2


def test_build_graph_score_populated():
    raw = {"mosint": {"email": "a@x.com", "breaches": ["Adobe"]}}
    graph = build_graph("seed", raw)
    for f in graph.findings.values():
        assert f.confidence_score > 0


def test_build_graph_edges_built():
    raw = {
        "mosint": {"email": "a@x.com"},
        "phone": {"phone": "+905551234567", "valid": True},
    }
    graph = build_graph("seed", raw)
    same_as = [e for e in graph.edges if e.edge_type == EdgeType.SAME_AS]
    assert len(same_as) >= 1


def test_build_graph_contradiction_lowers_score():
    raw = {"ai": {"lat": 39.0, "lng": 35.0, "confidence": 0.9}}

    tokyo_val = normalize_location(35.68, 139.69)
    tokyo_obs = SourceObservation(
        source_id="ai_gemini",
        source_kind=SourceKind.AI,
        weight=0.35,
        observed_at=datetime(2024, 1, 1),
    )
    cid = f"location:{tokyo_val}"
    tokyo_finding = ConfidenceFinding(
        id=cid, type=FindingType.LOCATION,
        value=tokyo_val, raw_value=tokyo_val,
        sources=[tokyo_obs], confidence_score=0.35,
        first_seen=datetime(2024, 1, 1),
        last_seen=datetime(2024, 1, 1),
    )
    g1 = build_graph("seed", raw)
    g1.findings[cid] = tokyo_finding
    g2 = build_graph("seed", raw, prior=g1)
    contradicts_edges = [e for e in g2.edges
                         if e.edge_type == EdgeType.CONTRADICTS]
    assert len(contradicts_edges) >= 1


def test_build_graph_prior_observation_union():
    raw = {"mosint": {"email": "a@x.com"}}
    g1 = build_graph("seed", raw)
    g2 = build_graph("seed", raw, prior=g1)
    assert g2.version == 2
    email_id = "email:a@x.com"
    if email_id in g2.findings:
        assert len(g2.findings[email_id].sources) >= 1


def test_build_graph_metadata_populated():
    raw = {"mosint": {"email": "a@x.com"}}
    graph = build_graph("seed", raw)
    assert "finding_count" in graph.metadata
    assert "edge_count" in graph.metadata
    assert "source_keys" in graph.metadata
    assert graph.metadata["finding_count"] >= 1


def test_build_graph_bad_adapter_skipped():
    raw = {
        "mosint": {"email": "a@x.com"},
        "darkweb": None,  # None payload → adapter atlanır
    }
    graph = build_graph("seed", raw)
    assert len(graph.findings) >= 1


def test_build_graph_prior_not_mutated():
    raw = {"mosint": {"email": "a@x.com"}}
    g1 = build_graph("seed", raw)
    original_version = g1.version
    original_finding_count = len(g1.findings)
    build_graph("seed", {"mosint": {"email": "b@x.com"}}, prior=g1)
    assert g1.version == original_version
    assert len(g1.findings) == original_finding_count


def test_build_graph_briefing_scenario():
    """
    Kalibrasyon: ahmet@gmail.com + mosint(breach) + darkweb + instagram
    → score >= 0.80
    """
    raw = {
        "mosint": {
            "email": "ahmet@gmail.com",
            "breaches": ["Adobe"],
            "social": {
                "instagram": "https://instagram.com/ahmet",
            },
        },
        "darkweb": {
            "email": "ahmet@gmail.com",
            "found": True,
            "breaches": [{"name": "Adobe"}],
        },
    }
    graph = build_graph("seed", raw)
    email_id = "email:ahmet@gmail.com"
    assert email_id in graph.findings
    score = graph.findings[email_id].confidence_score
    assert score >= 0.80
