"""Temporal cluster detection: group nearby TimelineEvents by time proximity.

Single-linkage: each event joins the current cluster if its timestamp is within
window_minutes of the previous event. Clusters with < 2 events are discarded.
"""

from typing import List, Optional

from app.models.temporal import TimelineCluster, TimelineEvent, TimelineEventType
from app.services.temporal import constants


def detect_clusters(
    events: List[TimelineEvent],
    window_minutes: Optional[int] = None,
) -> List[TimelineCluster]:
    if len(events) < 2:
        return []

    window = window_minutes if window_minutes is not None else constants.CLUSTER_WINDOW_MIN
    sorted_events = sorted(events, key=lambda e: e.timestamp)

    raw_clusters: List[List[TimelineEvent]] = []
    current: List[TimelineEvent] = [sorted_events[0]]

    for ev in sorted_events[1:]:
        delta = (ev.timestamp - current[-1].timestamp).total_seconds() / 60
        if delta <= window:
            current.append(ev)
        else:
            if len(current) >= 2:
                raw_clusters.append(current)
            current = [ev]
    if len(current) >= 2:
        raw_clusters.append(current)

    result = []
    for i, cluster in enumerate(raw_clusters):
        start = cluster[0].timestamp
        end = cluster[-1].timestamp
        span = int((end - start).total_seconds() // 60)
        result.append(TimelineCluster(
            cluster_id=f"cluster::{i}::{start.isoformat()}",
            start=start,
            end=end,
            span_minutes=span,
            event_ids=[e.event_id for e in cluster],
            event_types=list({e.event_type for e in cluster}),
        ))
    return result
