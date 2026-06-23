# app/services/confidence/adapters.py
"""Raw OSINT payload → ConfidenceFinding converters."""

from datetime import datetime, timezone
from typing import Any, Dict, List

from app.models.confidence import (
    ConfidenceFinding,
    FindingType,
    SourceKind,
    SourceObservation,
)
from app.services.confidence.normalizers import (
    canonical_id,
    normalize_domain,
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_username,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _make_obs(source_id: str, source_kind: SourceKind,
              weight: float, evidence_ref: str = None) -> SourceObservation:
    return SourceObservation(
        source_id=source_id,
        source_kind=source_kind,
        weight=weight,
        observed_at=_now(),
        evidence_ref=evidence_ref,
    )


def _make_finding(ftype: FindingType, raw_value: str,
                  normalized: str, obs: SourceObservation,
                  metadata: dict = None,
                  derived_from: str = None) -> ConfidenceFinding:
    cid = canonical_id(ftype, normalized)
    now = _now()
    return ConfidenceFinding(
        id=cid,
        type=ftype,
        value=normalized,
        raw_value=raw_value,
        sources=[obs],
        confidence_score=obs.weight,
        first_seen=now,
        last_seen=now,
        metadata=metadata or {},
        derived_from=derived_from,
    )


def mosint_to_findings(payload: Dict[str, Any]) -> List[ConfidenceFinding]:
    try:
        email_raw = payload.get("email", "")
        if not email_raw:
            return []
        results = []
        # EMAIL finding
        try:
            breaches = payload.get("breaches", [])
            has_breach = bool(breaches)
            kind = SourceKind.BREACH if has_breach else SourceKind.SCRAPING
            weight = 0.90 if has_breach else 0.40
            obs = _make_obs("mosint", kind, weight)
            email_norm = normalize_email(email_raw)
            f = _make_finding(
                FindingType.EMAIL, email_raw, email_norm, obs,
                metadata={
                    "mx_records": payload.get("mx_records", []),
                    "breaches": breaches,
                },
            )
            results.append(f)
        except Exception:
            pass
        # USERNAME findings from social
        social = payload.get("social", {}) or {}
        for platform, url in social.items():
            try:
                if not url:
                    continue
                obs = _make_obs(f"mosint_{platform}", SourceKind.SOCIAL, 0.50)
                # Use email prefix as username approximation
                username_raw = email_raw.split("@")[0]
                username_norm = normalize_username(username_raw)
                f = _make_finding(
                    FindingType.USERNAME, username_raw, username_norm, obs,
                    metadata={"platform": platform, "url": url},
                )
                results.append(f)
            except Exception:
                pass
        return results
    except Exception:
        return []


def darkweb_to_findings(payload: Dict[str, Any]) -> List[ConfidenceFinding]:
    try:
        email_raw = payload.get("email", "")
        found = payload.get("found", False)
        if not email_raw or not found:
            return []
        breaches = payload.get("breaches", [])
        obs = _make_obs("darkweb_hibp", SourceKind.BREACH, 0.90)
        email_norm = normalize_email(email_raw)
        f = _make_finding(
            FindingType.EMAIL, email_raw, email_norm, obs,
            metadata={
                "breach_count": len(breaches),
                "breach_names": [b["name"] for b in breaches if isinstance(b, dict)],
            },
        )
        return [f]
    except Exception:
        return []


def bios_to_findings(payload: Dict[str, Any]) -> List[ConfidenceFinding]:
    try:
        username_raw = payload.get("username", "")
        if not username_raw:
            return []
        results = []
        for item in payload.get("results", []):
            try:
                if item.get("status") != "exists":
                    continue
                platform = item.get("platform", "unknown")
                url = item.get("url", "")
                username_norm = normalize_username(username_raw)
                obs = _make_obs(f"bios_{platform}", SourceKind.SOCIAL, 0.50)
                results.append(_make_finding(
                    FindingType.USERNAME, username_raw, username_norm, obs,
                    metadata={"platform": platform, "url": url},
                ))
                display_name = item.get("display_name", "")
                if display_name:
                    obs_name = _make_obs(f"bios_{platform}_name", SourceKind.SOCIAL, 0.40)
                    name_norm = normalize_name(display_name)
                    results.append(_make_finding(
                        FindingType.NAME, display_name, name_norm, obs_name,
                        metadata={"platform": platform},
                    ))
            except Exception:
                pass
        return results
    except Exception:
        return []


def phone_to_findings(payload: Dict[str, Any]) -> List[ConfidenceFinding]:
    try:
        phone_raw = payload.get("phone", "")
        if not phone_raw:
            return []
        valid = payload.get("valid", False)
        kind = SourceKind.PHONE_VERIFIED if valid else SourceKind.SCRAPING
        weight = 0.85 if valid else 0.40
        obs = _make_obs("phone_numverify", kind, weight)
        phone_norm = normalize_phone(phone_raw)
        f = _make_finding(
            FindingType.PHONE, phone_raw, phone_norm, obs,
            metadata={
                "carrier": payload.get("carrier"),
                "line_type": payload.get("line_type"),
                "country_code": payload.get("country_code"),
            },
        )
        return [f]
    except Exception:
        return []


def domain_to_findings(payload: Dict[str, Any]) -> List[ConfidenceFinding]:
    try:
        domain_raw = payload.get("domain", "")
        if not domain_raw:
            return []
        results = []
        domain_norm = normalize_domain(domain_raw)
        domain_cid = canonical_id(FindingType.DOMAIN, domain_norm)
        # DOMAIN
        obs = _make_obs("domain_whois", SourceKind.WHOIS, 0.80)
        results.append(_make_finding(
            FindingType.DOMAIN, domain_raw, domain_norm, obs,
            metadata={
                "registrar": payload.get("registrar"),
                "created_date": payload.get("created_date"),
            },
        ))
        # EMAIL
        reg_email = payload.get("registrant_email", "")
        if reg_email:
            try:
                obs_e = _make_obs("domain_whois_email", SourceKind.WHOIS, 0.80)
                email_norm = normalize_email(reg_email)
                results.append(_make_finding(
                    FindingType.EMAIL, reg_email, email_norm, obs_e,
                    derived_from=domain_cid,
                ))
            except Exception:
                pass
        # NAME
        reg_name = payload.get("registrant_name", "")
        if reg_name:
            try:
                obs_n = _make_obs("domain_whois_name", SourceKind.WHOIS, 0.70)
                name_norm = normalize_name(reg_name)
                results.append(_make_finding(
                    FindingType.NAME, reg_name, name_norm, obs_n,
                ))
            except Exception:
                pass
        # IPs
        for ip in payload.get("ips", []):
            try:
                obs_ip = _make_obs("domain_whois_ip", SourceKind.WHOIS, 0.70)
                results.append(_make_finding(
                    FindingType.IP, ip, ip.strip(), obs_ip,
                ))
            except Exception:
                pass
        return results
    except Exception:
        return []


def ai_to_findings(payload: Dict[str, Any]) -> List[ConfidenceFinding]:
    try:
        lat = payload.get("lat")
        lng = payload.get("lng")
        if lat is None or lng is None:
            return []
        from app.services.confidence.normalizers import normalize_location
        loc_norm = normalize_location(float(lat), float(lng))
        obs = _make_obs("ai_gemini", SourceKind.AI, 0.35)
        f = _make_finding(
            FindingType.LOCATION, loc_norm, loc_norm, obs,
            metadata={
                "country": payload.get("estimated_country"),
                "region": payload.get("estimated_region"),
                "reasoning": payload.get("reasoning"),
            },
        )
        return [f]
    except Exception:
        return []
