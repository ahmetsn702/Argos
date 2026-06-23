# app/services/correlation/temporal.py
# -*- coding: utf-8 -*-
"""Timeline builder: aggregate date-bearing OSINT signals into a chronological
event list, detect breach clusters, and emit password-reuse rotation advice.

Cluster definition (single-linkage):
    A breach belongs to the same cluster as the previous one when their
    `BreachDate`s are at most CLUSTER_WINDOW_DAYS apart. A cluster is
    reported only when it contains at least CLUSTER_MIN_COUNT breaches.

Ethical guard (per user directive):
    `password_reuse_warnings` are emitted strictly in the form
    "<date> tarihinde <breach> ihlalinde parola sınıfı veri ifşa edildi.
     <Y platforms> hesaplarınızda da güncelleyin."
    No password content guess, no pattern inference, no value generation.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .models import Timeline, TimelineEvent, TimelineRequest

CLUSTER_WINDOW_DAYS = 90
CLUSTER_MIN_COUNT = 2

_DATE_FORMATS = (
    "%Y-%m-%d",
    "%Y/%m/%d",
    "%d-%m-%Y",
    "%d/%m/%Y",
    "%b %d, %Y",
    "%B %d, %Y",
    "%Y-%m-%dT%H:%M:%S",
)


# --- Date parsing -------------------------------------------------------------
def _parse_date(value: Any) -> Optional[datetime]:
    """Tolerant date parser. Returns naive UTC datetime or None."""
    if value is None:
        return None
    if isinstance(value, datetime):
        d = value
    else:
        s = str(value).strip()
        if not s:
            return None
        d = None
        # Try ISO 8601 first
        try:
            iso = s[:-1] + "+00:00" if s.endswith("Z") else s
            d = datetime.fromisoformat(iso)
        except ValueError:
            pass
        if d is None:
            for fmt in _DATE_FORMATS:
                try:
                    d = datetime.strptime(s, fmt)
                    break
                except ValueError:
                    continue
        if d is None:
            return None
    # Normalize to naive UTC for safe comparisons
    if d.tzinfo is not None:
        d = d.astimezone(timezone.utc).replace(tzinfo=None)
    return d


# --- Event extractors ---------------------------------------------------------
def _extract_breach_events(mosint: Optional[Dict[str, Any]]) -> List[TimelineEvent]:
    if not mosint:
        return []
    sources = mosint.get("sources") or {}
    hibp = sources.get("hibp") or {}
    if not hibp.get("ok"):
        return []
    events: List[TimelineEvent] = []
    for b in (hibp.get("data") or {}).get("breaches", []) or []:
        if not isinstance(b, dict):
            continue
        d = _parse_date(b.get("BreachDate"))
        if not d:
            continue
        events.append(TimelineEvent(
            date=d,
            event_type="breach",
            label=b.get("Name", "?"),
            source="hibp",
            metadata={"data_classes": list(b.get("DataClasses") or [])},
        ))
    return events


def _extract_domain_event(domain: Optional[Dict[str, Any]]) -> Optional[TimelineEvent]:
    if not domain:
        return None
    # Tolerate {"whois": {"ok": True, "data": {...}}}, {"whois": {...}}, or flat dict
    candidates = [
        ((domain.get("whois") or {}).get("data")),
        domain.get("whois"),
        domain,
    ]
    for c in candidates:
        if not isinstance(c, dict):
            continue
        cd = c.get("created_date") or c.get("creation_date") or c.get("created")
        d = _parse_date(cd)
        if d:
            return TimelineEvent(
                date=d,
                event_type="domain_registered",
                label=c.get("domain") or c.get("domain_name") or "domain",
                source="whois",
            )
    return None


def _extract_extra_events(extras: Optional[List[Dict[str, Any]]]) -> List[TimelineEvent]:
    if not extras:
        return []
    out: List[TimelineEvent] = []
    for e in extras:
        if not isinstance(e, dict):
            continue
        d = _parse_date(e.get("date"))
        if not d:
            continue
        out.append(TimelineEvent(
            date=d,
            event_type=e.get("event_type") or "custom",
            label=e.get("label") or "",
            source=e.get("source") or "user",
            metadata=dict(e.get("metadata") or {}),
        ))
    return out


# --- Cluster detection --------------------------------------------------------
def _detect_clusters(events: List[TimelineEvent]) -> List[Dict[str, Any]]:
    """Single-linkage cluster of breach events: each within CLUSTER_WINDOW_DAYS of
    the previous one. Cluster reported when it has >= CLUSTER_MIN_COUNT members."""
    breach_events = sorted(
        (e for e in events if e.event_type == "breach"),
        key=lambda e: e.date,
    )
    if not breach_events:
        return []

    clusters_raw: List[List[TimelineEvent]] = []
    current = [breach_events[0]]
    for e in breach_events[1:]:
        if (e.date - current[-1].date).days <= CLUSTER_WINDOW_DAYS:
            current.append(e)
        else:
            if len(current) >= CLUSTER_MIN_COUNT:
                clusters_raw.append(current)
            current = [e]
    if len(current) >= CLUSTER_MIN_COUNT:
        clusters_raw.append(current)

    return [
        {
            "start": c[0].date.isoformat(),
            "end": c[-1].date.isoformat(),
            "count": len(c),
            "span_days": (c[-1].date - c[0].date).days,
            "breaches": [e.label for e in c],
        }
        for c in clusters_raw
    ]


# --- Password-reuse warnings (ETHICAL: strict template only) ------------------
def _password_reuse_warnings(
    breach_dicts: List[Dict[str, Any]],
    bios: Optional[Dict[str, Any]],
) -> List[str]:
    """For each breach with a password class leak, emit a fixed-format warning.

    Format: "<date> tarihinde <breach> ihlalinde parola sınıfı veri ifşa edildi.
             Aynı parolayı kullanıyorsanız şu platformlarda da güncelleyin: <list>."

    NO password value, NO pattern inference, NO platform-specific guessing.
    """
    pw_classes = {"Passwords", "Password hashes"}
    pw_breaches = [
        b for b in breach_dicts
        if isinstance(b, dict) and pw_classes & set(b.get("DataClasses") or [])
    ]
    if not pw_breaches:
        return []

    platforms: List[str] = []
    if bios:
        results = bios.get("results") or []
        platforms = sorted({
            r.get("platform")
            for r in results
            if isinstance(r, dict) and r.get("status") == "exists" and r.get("platform")
        })

    warnings: List[str] = []
    for b in pw_breaches:
        date_str = b.get("BreachDate") or "?"
        name = b.get("Name") or "?"
        if platforms:
            warnings.append(
                f"{date_str} tarihinde {name} ihlalinde parola sınıfı veri ifşa edildi. "
                f"Aynı parolayı kullanıyorsanız şu platformlarda da güncelleyin: "
                f"{', '.join(platforms)}."
            )
        else:
            warnings.append(
                f"{date_str} tarihinde {name} ihlalinde parola sınıfı veri ifşa edildi. "
                f"Aynı parolayı kullandığınız tüm hesaplarda güncelleyin."
            )
    return warnings


# --- Public API ---------------------------------------------------------------
def build_timeline(req: TimelineRequest) -> Timeline:
    """Aggregate date-bearing OSINT signals into a Timeline object."""
    events: List[TimelineEvent] = []

    events.extend(_extract_breach_events(req.mosint))
    domain_event = _extract_domain_event(req.domain)
    if domain_event:
        events.append(domain_event)
    events.extend(_extract_extra_events(req.extra_events))

    events.sort(key=lambda e: e.date)

    span_years = 0.0
    if len(events) >= 2:
        delta_days = (events[-1].date - events[0].date).days
        span_years = round(delta_days / 365.25, 2)

    clusters = _detect_clusters(events)

    breach_dicts: List[Dict[str, Any]] = []
    if req.mosint:
        sources = req.mosint.get("sources") or {}
        hibp = sources.get("hibp") or {}
        if hibp.get("ok"):
            breach_dicts = list((hibp.get("data") or {}).get("breaches") or [])
    warnings = _password_reuse_warnings(breach_dicts, req.bios)

    return Timeline(
        events=events,
        span_years=span_years,
        breach_clusters=clusters,
        password_reuse_warnings=warnings,
    )


__all__ = ["build_timeline"]
