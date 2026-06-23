# app/services/pivot/expanders/email_expander.py
"""Expanders for FindingType.EMAIL."""

from datetime import datetime, timezone
from typing import List

from app.models.confidence import (
    ConfidenceFinding,
    FindingType,
    SourceKind,
    SourceObservation,
)
from app.services.confidence.adapters import (
    darkweb_to_findings,
    domain_to_findings,
    mosint_to_findings,
)
from app.services.confidence.normalizers import (
    canonical_id,
    normalize_domain,
    normalize_username,
)


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def expand_via_mosint(value: str) -> List[ConfidenceFinding]:
    try:
        from app.routers.mosint_api import mosint_full
        result = await mosint_full(email=value, timeout=8.0)
        if not isinstance(result, dict):
            return []
        # mosint_full returns nested {"sources": {...}}; flatten the email
        # so the existing adapter recognises the payload shape it expects.
        flat = dict(result)
        flat.setdefault("email", value)
        return mosint_to_findings(flat)
    except Exception:
        return []


async def expand_via_darkweb(value: str) -> List[ConfidenceFinding]:
    try:
        from app.services.darkweb_service import darkweb_osint
        result = await darkweb_osint(value, query_type="email", timeout=10.0)
        if not isinstance(result, dict):
            return []
        # Normalise to darkweb_to_findings shape: needs "email", "found", "breaches"
        payload = {
            "email": value,
            "found": bool(result.get("breaches")) or bool(result.get("found")),
            "breaches": result.get("breaches", []) or [],
        }
        return darkweb_to_findings(payload)
    except Exception:
        return []


async def expand_via_hibp(value: str) -> List[ConfidenceFinding]:
    try:
        from app.services.hibp_service import hibp_breached_account
        result = await hibp_breached_account(value, timeout=10.0)
        if not isinstance(result, dict):
            return []
        breaches = result.get("breaches") or result.get("data") or []
        if not breaches:
            return []
        payload = {
            "email": value,
            "found": True,
            "breaches": [
                {"name": b["Name"]} if isinstance(b, dict) and "Name" in b
                else {"name": str(b)}
                for b in breaches
            ],
        }
        return darkweb_to_findings(payload)
    except Exception:
        return []


async def expand_to_domain_from_email(value: str) -> List[ConfidenceFinding]:
    """email → owning domain finding (no network call)."""
    try:
        if "@" not in value:
            return []
        domain_raw = value.split("@", 1)[1]
        domain_norm = normalize_domain(domain_raw)
        if not domain_norm:
            return []
        return domain_to_findings({"domain": domain_norm})
    except Exception:
        return []


async def expand_to_username_candidates(value: str) -> List[ConfidenceFinding]:
    """email local-part → plausible username findings (no network call)."""
    try:
        if "@" not in value:
            return []
        local = value.split("@", 1)[0].lower()
        if not local or len(local) < 3:
            return []
        candidates = {local, local.replace(".", ""), local.replace("_", "")}
        out: List[ConfidenceFinding] = []
        now = _now()
        for cand in candidates:
            if len(cand) < 3:
                continue
            norm = normalize_username(cand)
            cid = canonical_id(FindingType.USERNAME, norm)
            obs = SourceObservation(
                source_id="pivot_email_local",
                source_kind=SourceKind.SCRAPING,
                weight=0.35,
                observed_at=now,
            )
            out.append(ConfidenceFinding(
                id=cid,
                type=FindingType.USERNAME,
                value=norm,
                raw_value=cand,
                sources=[obs],
                confidence_score=0.35,
                first_seen=now,
                last_seen=now,
                metadata={"derived_from_email": value},
            ))
        return out
    except Exception:
        return []
