# tests/test_confidence_contradictions.py
"""Tests for app/services/confidence/contradictions.py"""

from datetime import datetime

from app.models.confidence import (
    ConfidenceFinding,
    FindingType,
    SourceKind,
    SourceObservation,
)
from app.services.confidence.contradictions import (
    _haversine_km,
    _levenshtein_similarity,
    _location_contradicts,
    _name_contradicts,
    _phone_country_contradicts,
    detect_contradictions,
)
from app.services.confidence.normalizers import normalize_location

_NOW = datetime(2024, 1, 1, 12, 0, 0)


def make_location_finding(fid, lat, lng):
    value = normalize_location(lat, lng)
    return ConfidenceFinding(
        id=fid, type=FindingType.LOCATION,
        value=value, raw_value=value,
        sources=[], confidence_score=0.5,
        first_seen=_NOW, last_seen=_NOW,
    )


def make_phone_finding(fid, e164):
    return ConfidenceFinding(
        id=fid, type=FindingType.PHONE,
        value=e164, raw_value=e164,
        sources=[], confidence_score=0.5,
        first_seen=_NOW, last_seen=_NOW,
    )


def make_name_finding(fid, name):
    return ConfidenceFinding(
        id=fid, type=FindingType.NAME,
        value=name, raw_value=name,
        sources=[], confidence_score=0.5,
        first_seen=_NOW, last_seen=_NOW,
    )


# ── haversine ─────────────────────────────────────────────────────────────────

def test_haversine_istanbul_tokyo():
    km = _haversine_km(41.01, 28.95, 35.68, 139.69)
    assert km > 8000


def test_haversine_istanbul_kadikoy():
    km = _haversine_km(41.01, 28.95, 40.99, 29.03)
    assert km < 10


def test_haversine_same_point():
    assert _haversine_km(41.0, 29.0, 41.0, 29.0) == 0.0


# ── levenshtein ───────────────────────────────────────────────────────────────

def test_levenshtein_similarity_identical():
    assert _levenshtein_similarity("ahmet", "ahmet") == 1.0


def test_levenshtein_similarity_empty_both():
    assert _levenshtein_similarity("", "") == 1.0


def test_levenshtein_similarity_empty_one():
    assert _levenshtein_similarity("ahmet", "") == 0.0
    assert _levenshtein_similarity("", "ahmet") == 0.0


def test_levenshtein_similarity_ahmet_ahmed():
    # distance=1, max_len=5 → similarity=0.80 → no contradiction
    sim = _levenshtein_similarity("ahmet", "ahmed")
    assert abs(sim - 0.80) < 0.01


def test_levenshtein_similarity_ali_mehmet():
    # distance=5, max_len=6 → similarity≈0.167 → contradiction
    sim = _levenshtein_similarity("ali", "mehmet")
    assert sim < 0.5


# ── location contradictions ───────────────────────────────────────────────────

def test_location_far_contradicts():
    findings = {
        "loc:istanbul": make_location_finding("loc:istanbul", 41.01, 28.95),
        "loc:tokyo": make_location_finding("loc:tokyo", 35.68, 139.69),
    }
    result = detect_contradictions(findings)
    assert any(
        set([r[0], r[1]]) == {"loc:istanbul", "loc:tokyo"}
        for r in result
    )


def test_location_close_no_contradiction():
    findings = {
        "loc:kadikoy": make_location_finding("loc:kadikoy", 40.99, 29.03),
        "loc:besiktas": make_location_finding("loc:besiktas", 41.04, 29.01),
    }
    assert len(detect_contradictions(findings)) == 0


# ── phone contradictions ──────────────────────────────────────────────────────

def test_phone_different_country_contradicts():
    findings = {
        "phone:tr": make_phone_finding("phone:tr", "+905551234567"),
        "phone:us": make_phone_finding("phone:us", "+15551234567"),
    }
    result = detect_contradictions(findings)
    assert len(result) >= 1


def test_phone_same_country_no_contradiction():
    findings = {
        "phone:tr1": make_phone_finding("phone:tr1", "+905551234567"),
        "phone:tr2": make_phone_finding("phone:tr2", "+905559876543"),
    }
    assert len(detect_contradictions(findings)) == 0


# ── name contradictions ───────────────────────────────────────────────────────

def test_name_very_different_contradicts():
    # "ali" vs "mehmet" → sim≈0.167 < 0.5 → contradicts
    findings = {
        "name:ali": make_name_finding("name:ali", "ali"),
        "name:mehmet": make_name_finding("name:mehmet", "mehmet"),
    }
    result = detect_contradictions(findings)
    assert len(result) >= 1


def test_name_similar_no_contradiction():
    # "ahmet" vs "ahmed" → sim=0.80 → no contradiction
    findings = {
        "name:ahmet": make_name_finding("name:ahmet", "ahmet"),
        "name:ahmed": make_name_finding("name:ahmed", "ahmed"),
    }
    assert len(detect_contradictions(findings)) == 0


# ── manual flag ───────────────────────────────────────────────────────────────

def test_manual_flag_contradiction():
    obs = SourceObservation(
        source_id="darkweb_hibp",
        source_kind=SourceKind.BREACH,
        weight=0.9,
        observed_at=_NOW,
        contradicts=["other_finding_id"],
    )
    finding = ConfidenceFinding(
        id="email:test@x.com", type=FindingType.EMAIL,
        value="test@x.com", raw_value="test@x.com",
        sources=[obs], confidence_score=0.9,
        first_seen=_NOW, last_seen=_NOW,
    )
    result = detect_contradictions({"email:test@x.com": finding})
    assert any("email:test@x.com" in (r[0], r[1]) for r in result)


# ── email type — no auto contradiction ───────────────────────────────────────

def test_email_type_no_auto_contradiction():
    f1 = ConfidenceFinding(
        id="email:a@x.com", type=FindingType.EMAIL,
        value="a@x.com", raw_value="a@x.com",
        sources=[], confidence_score=0.5,
        first_seen=_NOW, last_seen=_NOW,
    )
    f2 = ConfidenceFinding(
        id="email:b@x.com", type=FindingType.EMAIL,
        value="b@x.com", raw_value="b@x.com",
        sources=[], confidence_score=0.5,
        first_seen=_NOW, last_seen=_NOW,
    )
    assert len(detect_contradictions({"email:a@x.com": f1, "email:b@x.com": f2})) == 0


# ── no mutations ──────────────────────────────────────────────────────────────

def test_detect_contradictions_no_mutation():
    findings = {
        "loc:tr": make_location_finding("loc:tr", 39.0, 35.0),
        "loc:jp": make_location_finding("loc:jp", 35.68, 139.69),
    }
    original_ids = set(findings.keys())
    detect_contradictions(findings)
    assert set(findings.keys()) == original_ids
