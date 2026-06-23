# app/routers/correlation.py
# -*- coding: utf-8 -*-
"""Correlation engine endpoints.

Phase 1: /correlation/identity
Phase 2: /correlation/risk
Phase 3: /correlation/timeline
Phase 4: /correlation/geo
Phase 5: /correlation/graph
Phase 6: /correlation/pivot
Phase 7: /correlation/full   (orchestration; no new service file)
"""

import asyncio
import time
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Body, HTTPException, Request

from app.core.limiter import limiter
from app.services.correlation.entity_resolver import resolve_identity
from app.services.correlation.geo_cluster import build_geo_cluster
from app.services.correlation.graph_builder import build_graph, to_vis_shape
from app.services.correlation.pivot_engine import run_pivot
from app.services.correlation.risk_scorer import score_risk
from app.services.correlation.temporal import build_timeline
from app.services.correlation.models import (
    FullRequest,
    FullResponse,
    GeoCluster,
    GeoRequest,
    GraphRequest,
    IdentityRequest,
    IdentityResponse,
    PivotRequest,
    PivotResult,
    ProfileInput,
    RiskAssessment,
    RiskRequest,
    Timeline,
    TimelineRequest,
)

router = APIRouter(prefix="/correlation", tags=["correlation"])


@router.post("/identity", response_model=IdentityResponse)
@limiter.limit("10/minute")
async def correlation_identity(
    request: Request,
    payload: IdentityRequest = Body(...),
) -> IdentityResponse:
    """Pairwise identity resolution for >=2 social profiles.

    Returns N*(N-1)/2 IdentityMatch objects with verdict ∈
    {likely_same, unclear, unlikely}.
    """
    if len(payload.profiles) < 2:
        raise HTTPException(status_code=400, detail="At least 2 profiles required")

    matches = resolve_identity(payload.profiles)
    n = len(payload.profiles)
    return IdentityResponse(matches=matches, pairs_evaluated=n * (n - 1) // 2)


@router.post("/risk", response_model=RiskAssessment)
@limiter.limit("10/minute")
async def correlation_risk(
    request: Request,
    payload: RiskRequest = Body(...),
) -> RiskAssessment:
    """Aggregate OSINT signals → 0-100 risk score + categorized findings.

    Body fields are all optional dicts; pass through raw JSON responses from
    /mosint/full, /darkweb/lookup, /username-bios, /phone/lookup.
    """
    return score_risk(payload)


@router.post("/timeline", response_model=Timeline)
@limiter.limit("15/minute")
async def correlation_timeline(
    request: Request,
    payload: TimelineRequest = Body(...),
) -> Timeline:
    """Build chronological event timeline from OSINT signals.

    Aggregates HIBP breach dates, domain whois creation dates, and any
    caller-supplied `extra_events`. Detects breach clusters (single-linkage
    90-day window, min 2) and emits password-rotation advice for breaches
    containing password class data.
    """
    return build_timeline(payload)


@router.post("/geo", response_model=GeoCluster)
@limiter.limit("15/minute")
async def correlation_geo(
    request: Request,
    payload: GeoRequest = Body(...),
) -> GeoCluster:
    """Bucket lat/lng signals into a coarse grid and report density clusters.

    Sources: `/domain/lookup` IP geo, `/geo/analyze-photo` EXIF GPS,
    caller-supplied phone coords, and `extra_points`. Default cell size is
    0.5° (~55km at the equator); tune via `cell_size_deg`.
    """
    return build_geo_cluster(payload)


@router.post("/graph")
@limiter.limit("10/minute")
async def correlation_graph(
    request: Request,
    payload: GraphRequest = Body(...),
):
    """Assemble OSINT signals + correlation outputs into a vis.js-compatible graph.

    Returns `{nodes: [...], edges: [...], metadata: {...}}` where each edge
    carries `from`/`to` (vis.js DataSet shape) plus `edge_type`.
    """
    return to_vis_shape(build_graph(payload))


@router.post("/pivot", response_model=PivotResult)
@limiter.limit("3/minute")
async def correlation_pivot(
    request: Request,
    payload: PivotRequest = Body(...),
) -> PivotResult:
    """Recursive OSINT pivot from a seed (email/username/phone).

    Hard limits: max_depth (1-3, default 2), max_entities_per_level (default 20),
    time_budget_seconds (≤180, default 60), seen-set loop protection.
    Rate-limited to 3 calls/min as the most expensive correlation endpoint.
    """
    return await run_pivot(payload)


# ============================================================ Phase 7 helpers
# Module-level so unittest.mock.patch can target a stable path.
async def _safe_mosint(email: str) -> Optional[Dict[str, Any]]:
    """Call /mosint/full's underlying function; return None on any failure."""
    try:
        from app.routers.mosint_api import mosint_full
        return await mosint_full(email=email, timeout=8.0)
    except Exception:
        return None


async def _safe_bios(username: str) -> Optional[Dict[str, Any]]:
    """Call _gather_bios in an executor and wrap in /username-bios shape."""
    try:
        from app.routers.bios import _gather_bios
        loop = asyncio.get_event_loop()
        results = await loop.run_in_executor(None, _gather_bios, username, None)
        return {
            "username": username,
            "count": len(results) if results else 0,
            "results": results or [],
        }
    except Exception:
        return None


async def _safe_domain(target: str) -> Optional[Dict[str, Any]]:
    """Call domain_osint; return None on any failure."""
    try:
        from app.services.domain_service import domain_osint
        return await domain_osint(target, timeout=8.0)
    except Exception:
        return None


def _bios_to_profiles(bios: Optional[Dict[str, Any]]) -> List[ProfileInput]:
    """Translate a /username-bios payload into ProfileInput list (status='exists' only)."""
    if not bios:
        return []
    username = bios.get("username") or ""
    out: List[ProfileInput] = []
    for r in bios.get("results") or []:
        if not isinstance(r, dict) or r.get("status") != "exists":
            continue
        platform = (r.get("platform") or "").lower()
        if not platform or not username:
            continue
        out.append(ProfileInput(
            platform=platform,
            username=username,
            display_name=r.get("display_name"),
            bio=r.get("bio"),
        ))
    return out


async def _resolve_raw(seed) -> Dict[str, Optional[Dict[str, Any]]]:
    """Fetch raw OSINT responses for the seed in parallel; tolerate failures."""
    raw: Dict[str, Optional[Dict[str, Any]]] = {"mosint": None, "bios": None, "domain": None}

    coros: List = []
    keys: List[str] = []

    if seed.email:
        coros.append(_safe_mosint(seed.email))
        keys.append("mosint")
    if seed.username:
        coros.append(_safe_bios(seed.username))
        keys.append("bios")
    if seed.email and "@" in seed.email:
        coros.append(_safe_domain(seed.email.split("@", 1)[1]))
        keys.append("domain")

    if not coros:
        return raw

    results = await asyncio.gather(*coros, return_exceptions=True)
    for k, r in zip(keys, results):
        if not isinstance(r, Exception):
            raw[k] = r
    return raw


@router.post("/full", response_model=FullResponse)
@limiter.limit("2/minute")
async def correlation_full(
    request: Request,
    payload: FullRequest = Body(...),
) -> FullResponse:
    """One-shot orchestration: resolve raw OSINT once, fan out to all modules.

    Rate-limited to 2/min (most expensive). Pivot is opt-in.
    """
    started = time.monotonic()

    # 1. Fan-in raw OSINT (parallel)
    raw = await _resolve_raw(payload.seed)

    # 2. Run sync (pure-Python) modules
    identity = None
    if payload.include_identity:
        profiles = _bios_to_profiles(raw.get("bios"))
        if len(profiles) >= 2:
            try:
                matches = resolve_identity(profiles)
                identity = IdentityResponse(
                    matches=matches,
                    pairs_evaluated=len(profiles) * (len(profiles) - 1) // 2,
                )
            except Exception:
                identity = None

    risk = None
    if payload.include_risk:
        try:
            risk = score_risk(RiskRequest(
                mosint=raw.get("mosint"),
                bios=raw.get("bios"),
            ))
        except Exception:
            risk = None

    timeline = None
    if payload.include_timeline:
        try:
            timeline = build_timeline(TimelineRequest(
                mosint=raw.get("mosint"),
                domain=raw.get("domain"),
            ))
        except Exception:
            timeline = None

    geo = None
    if payload.include_geo:
        try:
            geo = build_geo_cluster(GeoRequest(domain=raw.get("domain")))
        except Exception:
            geo = None

    graph = None
    if payload.include_graph:
        try:
            person_label = (payload.seed.email
                            or payload.seed.username
                            or payload.seed.phone)
            graph = to_vis_shape(build_graph(GraphRequest(
                person=person_label,
                mosint=raw.get("mosint"),
                bios=raw.get("bios"),
                domain=raw.get("domain"),
            )))
        except Exception:
            graph = None

    # 3. Optional async pivot
    pivot = None
    if payload.include_pivot:
        try:
            pivot = await run_pivot(PivotRequest(
                seed=payload.seed,
                max_depth=payload.pivot_max_depth,
                include_graph=False,
            ))
        except Exception:
            pivot = None

    took_ms = int((time.monotonic() - started) * 1000)

    # Confidence graph (opt-in)
    confidence_data = None
    if payload.include_confidence:
        try:
            from app.services.confidence.cache import default_cache
            seed = payload.seed
            seed_key = (
                f"email:{seed.email}" if seed.email
                else f"username:{seed.username}" if seed.username
                else f"phone:{seed.phone}" if seed.phone
                else "unknown"
            )
            raw_conf = {}
            if raw.get("mosint"):
                raw_conf["mosint"] = raw["mosint"]
            if raw.get("bios"):
                raw_conf["bios"] = raw["bios"]
            if raw.get("domain"):
                raw_conf["domain"] = raw["domain"]
            graph_c = default_cache.merge_and_save(
                seed_key=seed_key,
                raw=raw_conf,
                ttl_hours=1,
            )
            confidence_data = {
                "seed_key": graph_c.seed_key,
                "version": graph_c.version,
                "finding_count": len(graph_c.findings),
                "edge_count": len(graph_c.edges),
                "top_findings": [
                    {
                        "id": f.id,
                        "type": f.type.value,
                        "value": f.value,
                        "confidence_score": f.confidence_score,
                        "source_count": len(f.sources),
                    }
                    for f in sorted(
                        graph_c.findings.values(),
                        key=lambda x: x.confidence_score,
                        reverse=True,
                    )[:5]
                ],
            }
        except Exception:
            confidence_data = None

    return FullResponse(
        seed=payload.seed,
        raw_summary={k: (v is not None) for k, v in raw.items()},
        identity=identity,
        risk=risk,
        timeline=timeline,
        geo=geo,
        graph=graph,
        pivot=pivot,
        took_ms=took_ms,
        confidence=confidence_data,
    )
