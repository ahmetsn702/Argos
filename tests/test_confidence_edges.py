# tests/test_confidence_edges.py
"""Tests for app/services/confidence/edges.py"""

from datetime import datetime

from app.models.confidence import (
    ConfidenceFinding,
    EdgeType,
    FindingType,
)
from app.services.confidence.edges import build_edges
from app.services.confidence.normalizers import normalize_location

_NOW = datetime(2024, 1, 1, 12, 0, 0)


def make_finding(fid, ftype, value, score=0.5):
    return ConfidenceFinding(
        id=fid, type=ftype,
        value=value, raw_value=value,
        sources=[], confidence_score=score,
        first_seen=_NOW, last_seen=_NOW,
    )


def test_build_edges_empty():
    assert build_edges({}) == []


def test_same_as_email_phone():
    findings = {
        "email:a@x.com": make_finding(
            "email:a@x.com", FindingType.EMAIL, "a@x.com"),
        "phone:+905551234567": make_finding(
            "phone:+905551234567", FindingType.PHONE, "+905551234567"),
    }
    edges = build_edges(findings)
    same_as = [e for e in edges if e.edge_type == EdgeType.SAME_AS]
    assert len(same_as) >= 1


def test_same_as_email_username():
    findings = {
        "email:a@x.com": make_finding(
            "email:a@x.com", FindingType.EMAIL, "a@x.com"),
        "username:ahmet": make_finding(
            "username:ahmet", FindingType.USERNAME, "ahmet"),
    }
    edges = build_edges(findings)
    same_as = [e for e in edges if e.edge_type == EdgeType.SAME_AS]
    assert len(same_as) >= 1


def test_same_as_phone_username():
    findings = {
        "phone:+905551234567": make_finding(
            "phone:+905551234567", FindingType.PHONE, "+905551234567"),
        "username:ahmet": make_finding(
            "username:ahmet", FindingType.USERNAME, "ahmet"),
    }
    edges = build_edges(findings)
    same_as = [e for e in edges if e.edge_type == EdgeType.SAME_AS]
    assert len(same_as) >= 1


def test_no_same_as_two_emails():
    findings = {
        "email:a@x.com": make_finding(
            "email:a@x.com", FindingType.EMAIL, "a@x.com"),
        "email:b@x.com": make_finding(
            "email:b@x.com", FindingType.EMAIL, "b@x.com"),
    }
    edges = build_edges(findings)
    same_as = [e for e in edges if e.edge_type == EdgeType.SAME_AS]
    assert len(same_as) == 0


def test_contradicts_edge_from_location():
    findings = {
        "loc:tr": make_finding(
            "loc:tr", FindingType.LOCATION,
            normalize_location(39.0, 35.0)),
        "loc:jp": make_finding(
            "loc:jp", FindingType.LOCATION,
            normalize_location(35.68, 139.69)),
    }
    edges = build_edges(findings)
    contradicts = [e for e in edges if e.edge_type == EdgeType.CONTRADICTS]
    assert len(contradicts) >= 1


def test_no_duplicate_edges():
    findings = {
        "email:a@x.com": make_finding(
            "email:a@x.com", FindingType.EMAIL, "a@x.com"),
        "phone:+905551234567": make_finding(
            "phone:+905551234567", FindingType.PHONE, "+905551234567"),
        "username:ahmet": make_finding(
            "username:ahmet", FindingType.USERNAME, "ahmet"),
    }
    edges = build_edges(findings)
    seen = set()
    for e in edges:
        key = (e.source_id, e.target_id, e.edge_type)
        assert key not in seen, f"Duplicate edge: {key}"
        seen.add(key)


def test_same_as_weight_is_min_score():
    findings = {
        "email:a@x.com": make_finding(
            "email:a@x.com", FindingType.EMAIL, "a@x.com", score=0.8),
        "phone:+905551234567": make_finding(
            "phone:+905551234567", FindingType.PHONE, "+905551234567", score=0.6),
    }
    edges = build_edges(findings)
    same_as = [e for e in edges if e.edge_type == EdgeType.SAME_AS]
    assert len(same_as) >= 1
    assert abs(same_as[0].weight - 0.6) < 0.01


def test_contradicts_weight_is_one():
    findings = {
        "loc:tr": make_finding(
            "loc:tr", FindingType.LOCATION,
            normalize_location(39.0, 35.0)),
        "loc:jp": make_finding(
            "loc:jp", FindingType.LOCATION,
            normalize_location(35.68, 139.69)),
    }
    edges = build_edges(findings)
    contradicts = [e for e in edges if e.edge_type == EdgeType.CONTRADICTS]
    assert len(contradicts) >= 1
    assert contradicts[0].weight == 1.0


def test_build_edges_no_mutation():
    findings = {
        "email:a@x.com": make_finding(
            "email:a@x.com", FindingType.EMAIL, "a@x.com"),
        "phone:+905551234567": make_finding(
            "phone:+905551234567", FindingType.PHONE, "+905551234567"),
    }
    original_scores = {k: v.confidence_score for k, v in findings.items()}
    build_edges(findings)
    for k, f in findings.items():
        assert f.confidence_score == original_scores[k]
