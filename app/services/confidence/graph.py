# app/services/confidence/graph.py
"""Confidence graph builder — aggregates adapter findings into a ConfidenceGraph."""

import time
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.models.confidence import ConfidenceFinding, ConfidenceGraph, EdgeType
from app.services.confidence.adapters import (
    ai_to_findings,
    bios_to_findings,
    darkweb_to_findings,
    domain_to_findings,
    mosint_to_findings,
    phone_to_findings,
)
from app.services.confidence.edges import build_edges
from app.services.confidence.scoring import compute_score

_ADAPTERS = {
    "mosint": mosint_to_findings,
    "darkweb": darkweb_to_findings,
    "bios": bios_to_findings,
    "phone": phone_to_findings,
    "domain": domain_to_findings,
    "ai": ai_to_findings,
}


def _merge_findings(existing: ConfidenceFinding,
                    incoming: ConfidenceFinding) -> ConfidenceFinding:
    # Union sources — skip duplicate source_ids
    existing_source_ids = {obs.source_id for obs in existing.sources}
    merged_sources = list(existing.sources) + [
        obs for obs in incoming.sources
        if obs.source_id not in existing_source_ids
    ]
    # Dates
    first_seen = min(existing.first_seen, incoming.first_seen)
    last_seen = max(existing.last_seen, incoming.last_seen)
    # Metadata: existing wins (no overwrite)
    merged_meta = dict(incoming.metadata)
    merged_meta.update(existing.metadata)
    # Lists union
    contradicted_by = list({*existing.contradicted_by, *incoming.contradicted_by})
    corroborated_by = list({*existing.corroborated_by, *incoming.corroborated_by})
    derived_from = existing.derived_from or incoming.derived_from

    return existing.model_copy(update={
        "sources": merged_sources,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "metadata": merged_meta,
        "contradicted_by": contradicted_by,
        "corroborated_by": corroborated_by,
        "derived_from": derived_from,
    })


def build_graph(
    seed_key: str,
    raw: Dict[str, Any],
    prior: Optional[ConfidenceGraph] = None,
) -> ConfidenceGraph:
    t0 = time.monotonic()

    findings: Dict[str, ConfidenceFinding] = {}

    # Seed from prior (copy — don't mutate prior)
    if prior:
        for fid, f in prior.findings.items():
            findings[fid] = f.model_copy(deep=True)

    # Run adapters
    for key, adapter in _ADAPTERS.items():
        payload = raw.get(key)
        if payload is None:
            continue
        try:
            new_findings = adapter(payload)
        except Exception:
            continue
        for f in new_findings:
            if f.id in findings:
                findings[f.id] = _merge_findings(findings[f.id], f)
            else:
                findings[f.id] = f

    # Build edges
    edges = build_edges(findings)

    # Update contradicted_by from CONTRADICTS edges
    for edge in edges:
        if edge.edge_type != EdgeType.CONTRADICTS:
            continue
        src = findings.get(edge.source_id)
        tgt = findings.get(edge.target_id)
        if src and edge.target_id not in src.contradicted_by:
            src.contradicted_by.append(edge.target_id)
        if tgt and edge.source_id not in tgt.contradicted_by:
            tgt.contradicted_by.append(edge.source_id)

    # Compute scores
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    for f in findings.values():
        score = compute_score(f, now=now)
        f.confidence_score = score

    version = (prior.version + 1) if prior else 1
    took_ms = round((time.monotonic() - t0) * 1000, 1)

    return ConfidenceGraph(
        seed_key=seed_key,
        findings=findings,
        edges=edges,
        computed_at=now,
        version=version,
        metadata={
            "took_ms": took_ms,
            "finding_count": len(findings),
            "edge_count": len(edges),
            "source_keys": list(raw.keys()),
        },
    )
