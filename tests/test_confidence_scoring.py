# tests/test_confidence_scoring.py
"""Tests for app/services/confidence/scoring.py"""

from datetime import datetime, timedelta

from app.models.confidence import (
    ConfidenceFinding,
    FindingType,
    SourceKind,
    SourceObservation,
)
from app.services.confidence.scoring import apply_aging, compute_score, noisy_or

_REF = datetime(2024, 1, 1, 12, 0, 0)


def make_finding(sources, contradicted_by=None):
    return ConfidenceFinding(
        id="email:test@example.com",
        type=FindingType.EMAIL,
        value="test@example.com",
        raw_value="test@example.com",
        sources=sources,
        confidence_score=0.0,
        first_seen=_REF,
        last_seen=_REF,
        contradicted_by=contradicted_by or [],
    )


def make_obs(source_id, source_kind, days_ago=0):
    return SourceObservation(
        source_id=source_id,
        source_kind=source_kind,
        weight=0.5,
        observed_at=_REF - timedelta(days=days_ago),
    )


# ── noisy_or ──────────────────────────────────────────────────────────────────

def test_noisy_or_empty():
    assert noisy_or([]) == 0.0


def test_noisy_or_single():
    assert noisy_or([0.5]) == 0.5


def test_noisy_or_two_independent():
    # 1 - (0.5 * 0.5) = 0.75
    assert abs(noisy_or([0.5, 0.5]) - 0.75) < 0.001


def test_noisy_or_diminishing_returns():
    result = noisy_or([0.3] * 20)
    assert result < 1.0
    assert result > 0.99


def test_noisy_or_clamps_over_one():
    # input > 1 clamped to 1.0 → result = 1.0
    assert noisy_or([1.5]) == 1.0


def test_noisy_or_clamps_negative():
    # input < 0 clamped to 0.0 → noisy_or([0.0]) = 0.0
    assert noisy_or([-0.5]) == 0.0


# ── apply_aging ───────────────────────────────────────────────────────────────

def test_apply_aging_no_decay():
    obs_time = datetime(2024, 1, 1)
    now = datetime(2024, 6, 1)
    assert apply_aging(0.5, obs_time, now, aging_rate=1.0) == 0.5


def test_apply_aging_30_days():
    obs_time = datetime(2024, 1, 1)
    now = datetime(2024, 1, 31)
    result = apply_aging(0.5, obs_time, now, aging_rate=0.95)
    assert abs(result - 0.5 * (0.95 ** 30)) < 0.001


def test_apply_aging_same_day():
    assert apply_aging(0.7, _REF, _REF, aging_rate=0.95) == 0.7


def test_apply_aging_future_timestamp():
    # future observed_at → days_old clamped to 0 → weight unchanged
    future = _REF + timedelta(days=5)
    assert apply_aging(0.6, future, _REF, aging_rate=0.95) == 0.6


# ── compute_score ─────────────────────────────────────────────────────────────

def test_empty_sources():
    finding = make_finding([])
    assert compute_score(finding, now=_REF) == 0.0


def test_single_source_no_aging():
    obs = SourceObservation(
        source_id="web_scraping",
        source_kind=SourceKind.SCRAPING,
        weight=0.5,
        observed_at=_REF,
    )
    score = compute_score(
        make_finding([obs]),
        now=_REF,
        weights_dict={"web_scraping": 0.40},
    )
    assert abs(score - 0.40) < 0.01


def test_two_sources_different_kinds():
    obs1 = SourceObservation(source_id="darkweb_hibp",
                             source_kind=SourceKind.BREACH,
                             weight=0.9, observed_at=_REF)
    obs2 = SourceObservation(source_id="social_unverified",
                             source_kind=SourceKind.SOCIAL,
                             weight=0.5, observed_at=_REF)
    score = compute_score(
        make_finding([obs1, obs2]),
        now=_REF,
        weights_dict={"darkweb_hibp": 0.90, "social_unverified": 0.50},
    )
    assert score >= 0.95


def test_three_sources_same_kind_no_bonus():
    sources_same = [
        SourceObservation(source_id=f"social_{i}", source_kind=SourceKind.SOCIAL,
                          weight=0.5, observed_at=_REF)
        for i in range(3)
    ]
    score_same = compute_score(
        make_finding(sources_same),
        now=_REF,
        weights_dict={f"social_{i}": 0.5 for i in range(3)},
    )

    sources_diff = [
        SourceObservation(source_id="darkweb_hibp", source_kind=SourceKind.BREACH,
                          weight=0.5, observed_at=_REF),
        SourceObservation(source_id="phone_verified", source_kind=SourceKind.PHONE_VERIFIED,
                          weight=0.5, observed_at=_REF),
        SourceObservation(source_id="social_v", source_kind=SourceKind.SOCIAL_VERIFIED,
                          weight=0.5, observed_at=_REF),
    ]
    score_diff = compute_score(
        make_finding(sources_diff),
        now=_REF,
        weights_dict={"darkweb_hibp": 0.5, "phone_verified": 0.5, "social_v": 0.5},
    )
    assert score_diff > score_same


def test_contradicts_penalty():
    obs = SourceObservation(source_id="darkweb_hibp", source_kind=SourceKind.BREACH,
                            weight=0.9, observed_at=_REF)
    score = compute_score(
        make_finding([obs], contradicted_by=["other_finding_id"]),
        now=_REF,
        weights_dict={"darkweb_hibp": 0.90},
    )
    # base=0.90, penalty=0.15 → 0.75
    assert abs(score - 0.75) < 0.02


def test_contradicts_penalty_clamp():
    obs = SourceObservation(source_id="darkweb_hibp", source_kind=SourceKind.BREACH,
                            weight=0.9, observed_at=_REF)
    score = compute_score(
        make_finding([obs], contradicted_by=["a", "b", "c", "d", "e"]),
        now=_REF,
        weights_dict={"darkweb_hibp": 0.90},
    )
    # penalty capped at 0.45 → base 0.90 - 0.45 = 0.45
    assert abs(score - 0.45) < 0.02


def test_score_clamp_lower_bound():
    obs = SourceObservation(source_id="ai_gemini", source_kind=SourceKind.AI,
                            weight=0.35, observed_at=_REF)
    score = compute_score(
        make_finding([obs], contradicted_by=["a", "b", "c", "d", "e", "f"]),
        now=_REF,
        weights_dict={"ai_gemini": 0.35},
    )
    assert score >= 0.0


def test_compute_score_no_mutation():
    # finding.confidence_score mutate edilmemeli
    obs = SourceObservation(source_id="darkweb_hibp", source_kind=SourceKind.BREACH,
                            weight=0.9, observed_at=_REF)
    finding = make_finding([obs])
    original_score = finding.confidence_score
    compute_score(finding, now=_REF, weights_dict={"darkweb_hibp": 0.90})
    assert finding.confidence_score == original_score
