# tests/test_confidence_summary.py
"""Tests for app/services/confidence/summary.py"""

from datetime import datetime

from app.models.confidence import (
    ConfidenceFinding,
    ConfidenceGraph,
    FindingType,
    SourceKind,
    SourceObservation,
)
from app.services.confidence.summary import confidence_summary

_NOW = datetime(2024, 1, 1, 12, 0, 0)


def _make_finding(fid, score, sources_n=1, contradicted_by=None,
                  ftype=FindingType.EMAIL):
    obs = [
        SourceObservation(
            source_id=f"src_{i}",
            source_kind=SourceKind.SCRAPING,
            weight=0.5,
            observed_at=_NOW,
        )
        for i in range(sources_n)
    ]
    return ConfidenceFinding(
        id=fid, type=ftype,
        value=fid, raw_value=fid,
        sources=obs,
        confidence_score=score,
        first_seen=_NOW, last_seen=_NOW,
        contradicted_by=contradicted_by or [],
    )


def _make_graph(findings_dict):
    return ConfidenceGraph(
        seed_key="test",
        findings=findings_dict,
        edges=[],
        computed_at=_NOW,
        version=1,
    )


def test_summary_empty_graph():
    result = confidence_summary(_make_graph({}))
    assert result["high_confidence"] == []
    assert result["medium_confidence"] == []
    assert result["low_confidence"] == []
    assert result["contradicted"] == []
    assert result["single_source"] == []
    assert result["stats"]["total_findings"] == 0
    assert result["stats"]["avg_score"] == 0.0


def test_summary_high_confidence_bucket():
    findings = {
        "f1": _make_finding("f1", score=0.90),
        "f2": _make_finding("f2", score=0.60),
        "f3": _make_finding("f3", score=0.30),
    }
    result = confidence_summary(_make_graph(findings))
    assert len(result["high_confidence"]) == 1
    assert result["high_confidence"][0]["id"] == "f1"


def test_summary_medium_confidence_bucket():
    findings = {
        "f1": _make_finding("f1", score=0.75),
        "f2": _make_finding("f2", score=0.50),
    }
    result = confidence_summary(_make_graph(findings))
    assert len(result["medium_confidence"]) == 2


def test_summary_contradicted_bucket():
    findings = {
        "f1": _make_finding("f1", score=0.80, contradicted_by=["f2"]),
        "f2": _make_finding("f2", score=0.70),
    }
    result = confidence_summary(_make_graph(findings))
    contradicted_ids = [f["id"] for f in result["contradicted"]]
    assert "f1" in contradicted_ids
    assert "f2" not in contradicted_ids


def test_summary_single_source_bucket():
    findings = {
        "f1": _make_finding("f1", score=0.50, sources_n=1),
        "f2": _make_finding("f2", score=0.50, sources_n=3),
    }
    result = confidence_summary(_make_graph(findings))
    single_ids = [f["id"] for f in result["single_source"]]
    assert "f1" in single_ids
    assert "f2" not in single_ids


def test_summary_stats_correct():
    findings = {
        "h": _make_finding("h", score=0.90),
        "m": _make_finding("m", score=0.65),
        "l": _make_finding("l", score=0.30),
    }
    result = confidence_summary(_make_graph(findings))
    stats = result["stats"]
    assert stats["total_findings"] == 3
    assert stats["high_count"] == 1
    assert stats["medium_count"] == 1
    assert stats["low_count"] == 1
    # avg = (0.90 + 0.65 + 0.30) / 3 ≈ 0.617
    assert abs(stats["avg_score"] - 0.62) < 0.01


def test_summary_sorted_by_score_desc():
    findings = {
        "f3": _make_finding("f3", score=0.30),
        "f1": _make_finding("f1", score=0.90),
        "f2": _make_finding("f2", score=0.60),
    }
    result = confidence_summary(_make_graph(findings))
    all_scores = (
        [f["score"] for f in result["high_confidence"]]
        + [f["score"] for f in result["medium_confidence"]]
        + [f["score"] for f in result["low_confidence"]]
    )
    assert all_scores == sorted(all_scores, reverse=True)
