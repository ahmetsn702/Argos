"""Temporal Intelligence orchestrator.

analyze(seed_key, narrative, force) → Optional[TemporalAnalysis]

Steps:
1. Cache hit (unless force=True) → return cached
2. Load ConfidenceGraph from confidence cache → None if missing
3. extract_events → detect_clusters → detect_all
4. If narrative=True and anomalies non-empty → call narrator
5. Build TemporalAnalysis, store in cache, return
"""

import time
from datetime import datetime, timezone
from typing import Optional

from app.models.temporal import TemporalAnalysis
from app.services.confidence.cache import default_cache
from app.services.temporal.anomalies import detect_all
from app.services.temporal.cache import default_temporal_cache
from app.services.temporal.clusters import detect_clusters
from app.services.temporal.extractors import extract_events
from app.services.temporal.narrator import TemporalNarrator


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def analyze(
    seed_key: str,
    narrative: bool = False,
    force: bool = False,
) -> Optional[TemporalAnalysis]:
    # 1. Cache hit
    if not force:
        cached = default_temporal_cache.get(seed_key)
        if cached is not None:
            return cached

    # 2. Load ConfidenceGraph
    graph = default_cache.get(seed_key)
    if graph is None:
        return None

    t0 = time.monotonic()

    # 3. Extract → cluster → anomalies
    events = extract_events(graph)
    clusters = detect_clusters(events)
    anomalies = detect_all(events)

    # 4. Narrative (only if requested AND anomalies exist)
    narr = None
    if narrative and anomalies:
        narr = await TemporalNarrator().generate(events, anomalies)

    took_ms = round((time.monotonic() - t0) * 1000, 1)

    analysis = TemporalAnalysis(
        seed_key=seed_key,
        events=events,
        clusters=clusters,
        anomalies=anomalies,
        narrative=narr,
        computed_at=_now(),
        metadata={
            "took_ms": took_ms,
            "event_count": len(events),
            "cluster_count": len(clusters),
            "anomaly_count": len(anomalies),
            "graph_version": graph.version,
        },
    )

    # 5. Cache & return
    if force:
        default_temporal_cache.invalidate(seed_key)
    default_temporal_cache.put(analysis)
    return analysis
