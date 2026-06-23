# app/services/correlation/risk_scorer.py
# -*- coding: utf-8 -*-
"""Risk scoring: aggregate OSINT signals → 0-100 score + categorized findings.

Categories (max contribution):
- breach_exposure       (40)
- sensitive_data_leak   (20)
- profile_sprawl        (20)
- email_reputation      (10)
- phone_exposure        (10)

Bands: low (<25) | medium (<50) | high (<75) | critical (>=75)

Ethical guards (Phase 2):
- Sensitive class detection only emits CATEGORY names ("Passwords",
  "Credit cards") — never the actual value.
- Recommendations advise password rotation and 2FA in plain language.
  No password pattern inference, no candidate value generation,
  no per-platform guesses beyond breach metadata names.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional, Tuple

from .models import Finding, RiskAssessment, RiskBand, RiskRequest


# --- Tunables ----------------------------------------------------------------
MAX_BREACH_COUNT = 40
MAX_SENSITIVE_DATA = 20
MAX_PROFILE_SPRAWL = 20
MAX_EMAIL_REPUTATION = 10
MAX_PHONE_EXPOSURE = 10

# Sensitive HIBP/data class weights. Sum capped at MAX_SENSITIVE_DATA.
_SENSITIVE_CLASS_WEIGHTS: Dict[str, int] = {
    "Passwords": 10,
    "Password hashes": 6,
    "Password hints": 4,
    "Credit cards": 8,
    "Bank accounts": 8,
    "Bank account numbers": 8,
    "SSN": 10,
    "Social security numbers": 10,
    "Government issued IDs": 7,
    "Auth tokens": 6,
    "Security questions and answers": 5,
    "Private messages": 5,
    "Phone numbers": 3,
    "Physical addresses": 4,
    "Date of birth": 4,
    "Dates of birth": 4,
}


# --- Helpers -----------------------------------------------------------------
def _band_for(score: int) -> RiskBand:
    if score < 25:
        return RiskBand.LOW
    if score < 50:
        return RiskBand.MEDIUM
    if score < 75:
        return RiskBand.HIGH
    return RiskBand.CRITICAL


def _severity(score: int, max_score: int) -> str:
    if score == 0 or max_score == 0:
        return "info"
    ratio = score / max_score
    if ratio >= 0.75:
        return "critical"
    if ratio >= 0.5:
        return "high"
    if ratio >= 0.25:
        return "warn"
    return "info"


# --- Extractors --------------------------------------------------------------
def _extract_breaches(
    mosint: Optional[Dict[str, Any]],
    darkweb: Optional[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Pull breach entries from `/mosint/full` HIBP section and tolerate
    common `/darkweb/lookup` shapes."""
    breaches: List[Dict[str, Any]] = []
    if mosint:
        sources = mosint.get("sources") or {}
        hibp = sources.get("hibp") or {}
        if hibp.get("ok"):
            data = hibp.get("data") or {}
            for b in (data.get("breaches") or []):
                if isinstance(b, dict):
                    breaches.append(b)
    if darkweb:
        for key in ("leakcheck", "data", "results"):
            section = darkweb.get(key)
            if not section:
                continue
            if isinstance(section, dict):
                items = (section.get("result")
                         or section.get("results")
                         or section.get("breaches")
                         or [])
            elif isinstance(section, list):
                items = section
            else:
                continue
            for r in items:
                if isinstance(r, dict):
                    breaches.append({
                        "Name": r.get("Name") or r.get("source") or r.get("name") or "darkweb_leak",
                        "BreachDate": r.get("BreachDate") or r.get("date"),
                        "DataClasses": r.get("DataClasses") or r.get("fields") or r.get("data_classes") or [],
                    })
    return breaches


# --- Per-category scorers ----------------------------------------------------
def _breach_count_score(n: int) -> int:
    if n == 0:
        return 0
    if n <= 1:
        return 10
    if n <= 3:
        return 20
    if n <= 6:
        return 30
    return MAX_BREACH_COUNT


def _sensitive_data_score(breaches: List[Dict[str, Any]]) -> Tuple[int, List[str]]:
    found_classes = set()
    for b in breaches:
        for c in (b.get("DataClasses") or []):
            if c in _SENSITIVE_CLASS_WEIGHTS:
                found_classes.add(c)
    if not found_classes:
        return 0, []
    total = sum(_SENSITIVE_CLASS_WEIGHTS[c] for c in found_classes)
    score = min(MAX_SENSITIVE_DATA, total)
    evidence = [f"sensitive class leaked: {c}" for c in sorted(found_classes)]
    return score, evidence


def _profile_sprawl_score(bios: Optional[Dict[str, Any]]) -> Tuple[int, List[str]]:
    if not bios:
        return 0, []
    results = bios.get("results") or []
    found = [r for r in results if isinstance(r, dict) and r.get("status") == "exists"]
    n = len(found)
    if n == 0:
        return 0, []
    score = min(MAX_PROFILE_SPRAWL, n * 3)
    platforms = sorted({r.get("platform", "?") for r in found})
    return score, [f"discovered on {n} platforms: {', '.join(platforms)}"]


def _email_reputation_score(mosint: Optional[Dict[str, Any]]) -> Tuple[int, List[str]]:
    if not mosint:
        return 0, []
    er = (mosint.get("sources") or {}).get("emailrep") or {}
    data = er.get("data") or {}
    if not data:
        return 0, []
    score = 0
    evidence: List[str] = []
    if data.get("suspicious"):
        score += 5
        evidence.append("emailrep flagged as suspicious")
    details = data.get("details") or {}
    if details.get("malicious_activity"):
        score += 5
        evidence.append("malicious activity history")
    if details.get("disposable"):
        score += 3
        evidence.append("disposable email domain")
    if details.get("credentials_leaked"):
        score += 2
        evidence.append("credentials previously leaked")
    return min(MAX_EMAIL_REPUTATION, score), evidence


def _phone_exposure_score(
    phone: Optional[Dict[str, Any]],
    darkweb: Optional[Dict[str, Any]],
) -> Tuple[int, List[str]]:
    score = 0
    evidence: List[str] = []
    if phone:
        nv = phone.get("numverify") or {}
        if nv.get("valid"):
            if nv.get("carrier"):
                score += 2
                evidence.append(f"carrier exposed: {nv.get('carrier')}")
            if nv.get("location"):
                score += 2
                evidence.append(f"location exposed: {nv.get('location')}")
    if darkweb:
        summary = darkweb.get("summary") or {}
        leak_count = summary.get("leak_count") or summary.get("count") or 0
        if isinstance(leak_count, (int, float)) and leak_count > 0:
            score += 6
            evidence.append(f"phone or related identifier in {int(leak_count)} leak(s)")
    return min(MAX_PHONE_EXPOSURE, score), evidence


# --- Recommendations ---------------------------------------------------------
def _build_recommendations(
    findings: List[Finding],
    breaches: List[Dict[str, Any]],
) -> List[str]:
    """Build action-oriented recommendations.

    Ethical constraint: NO password pattern inference. Only advise rotation
    and breach awareness.
    """
    recs: List[str] = []
    cats = {f.category for f in findings}

    if "sensitive_data_leak" in cats:
        # Password class breaches → name-only rotation advice
        pw_breaches = [b for b in breaches
                       if "Passwords" in (b.get("DataClasses") or [])
                       or "Password hashes" in (b.get("DataClasses") or [])]
        if pw_breaches:
            names = ", ".join(b.get("Name", "?") for b in pw_breaches[:5])
            recs.append(
                f"Parola sınıfı veri şu ihlallerde ifşa edildi: {names}. "
                f"Bu platformlarda parolanızı güncelleyin; aynı parolayı başka "
                f"hesaplarda kullandıysanız oralarda da değiştirin."
            )

        cc_breaches = [b for b in breaches
                       if any(c in (b.get("DataClasses") or [])
                              for c in ("Credit cards", "Bank accounts", "Bank account numbers"))]
        if cc_breaches:
            recs.append(
                "Kredi kartı/banka hesabı bilgileri ifşa edilmiş. Kart "
                "sağlayıcınıza durumu bildirin ve hesap hareketlerinizi izleyin."
            )

    if "breach_exposure" in cats:
        recs.append(
            "Dijital hesaplarınızda 2FA (iki faktörlü kimlik doğrulama) etkinleştirin."
        )

    if "profile_sprawl" in cats:
        recs.append(
            "Birden fazla platformda görünür durumdasınız; gizlilik ayarlarınızı "
            "gözden geçirip kullanmadığınız hesapları kapatmayı düşünün."
        )

    if "email_reputation" in cats:
        recs.append(
            "Email itibarınız düşük; spam listelerine düşmüş olabilirsiniz. "
            "Önemli iletişimler için ikinci bir email kullanmayı düşünün."
        )

    return recs


# --- Public API --------------------------------------------------------------
def score_risk(req: RiskRequest) -> RiskAssessment:
    """Aggregate OSINT signals into 0-100 risk score with categorized findings."""
    findings: List[Finding] = []
    total = 0

    breaches = _extract_breaches(req.mosint, req.darkweb)

    # 1. Breach count
    bc_score = _breach_count_score(len(breaches))
    if bc_score > 0:
        findings.append(Finding(
            category="breach_exposure",
            severity=_severity(bc_score, MAX_BREACH_COUNT),
            label=f"{len(breaches)} veri ihlalinde tespit edildi",
            evidence=[f"breach: {b.get('Name', '?')}" for b in breaches[:5]],
            weight=bc_score,
        ))
        total += bc_score

    # 2. Sensitive data classes
    sd_score, sd_evidence = _sensitive_data_score(breaches)
    if sd_score > 0:
        findings.append(Finding(
            category="sensitive_data_leak",
            severity=_severity(sd_score, MAX_SENSITIVE_DATA),
            label="Hassas veri sınıfları ifşa edildi",
            evidence=sd_evidence,
            weight=sd_score,
        ))
        total += sd_score

    # 3. Profile sprawl
    ps_score, ps_evidence = _profile_sprawl_score(req.bios)
    if ps_score > 0:
        findings.append(Finding(
            category="profile_sprawl",
            severity=_severity(ps_score, MAX_PROFILE_SPRAWL),
            label="Çok sayıda platformda görünür hesap",
            evidence=ps_evidence,
            weight=ps_score,
        ))
        total += ps_score

    # 4. Email reputation
    er_score, er_evidence = _email_reputation_score(req.mosint)
    if er_score > 0:
        findings.append(Finding(
            category="email_reputation",
            severity=_severity(er_score, MAX_EMAIL_REPUTATION),
            label="Email itibar/risk göstergesi",
            evidence=er_evidence,
            weight=er_score,
        ))
        total += er_score

    # 5. Phone exposure
    pe_score, pe_evidence = _phone_exposure_score(req.phone, req.darkweb)
    if pe_score > 0:
        findings.append(Finding(
            category="phone_exposure",
            severity=_severity(pe_score, MAX_PHONE_EXPOSURE),
            label="Telefon ifşa göstergeleri",
            evidence=pe_evidence,
            weight=pe_score,
        ))
        total += pe_score

    score = min(100, total)
    band = _band_for(score)
    recommendations = _build_recommendations(findings, breaches)

    return RiskAssessment(
        score=score,
        band=band,
        findings=findings,
        recommendations=recommendations,
    )


__all__ = ["score_risk"]
