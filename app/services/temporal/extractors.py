"""Extract TimelineEvents from a ConfidenceGraph.

Rules (multi-event per finding):
- EMAIL + metadata.breaches  → one BREACH event per breach entry
                               + one BREACH_PASSWORD if "Passwords"/"Password hashes" in DataClasses
- DOMAIN + metadata.created_date → DOMAIN_REGISTERED event
- USERNAME/SOCIAL + metadata.platform → SOCIAL_ACTIVITY event (timestamp = first_seen)
- Every finding → FIRST_OBSERVED event (timestamp = first_seen)
parse_temporal failures are silently skipped.
Output is sorted ascending by timestamp.
"""

import logging
from typing import Any, Dict, List

from app.models.confidence import ConfidenceGraph, FindingType
from app.models.temporal import TimelineEvent, TimelineEventType
from app.services.temporal.parsing import parse_temporal

logger = logging.getLogger(__name__)

_PASSWORD_CLASSES = {"Passwords", "Password hashes"}


def _event(finding_id: str, etype: TimelineEventType, ts, confidence: float,
           source: str, metadata: Dict[str, Any], idx: int) -> TimelineEvent:
    return TimelineEvent(
        event_id=f"{finding_id}::{etype.value}::{idx}",
        finding_id=finding_id,
        event_type=etype,
        timestamp=ts,
        confidence=confidence,
        source=source,
        metadata=metadata,
    )


def extract_events(graph: ConfidenceGraph) -> List[TimelineEvent]:
    events: List[TimelineEvent] = []

    for fid, finding in graph.findings.items():
        conf = finding.confidence_score
        idx = 0

        # --- FIRST_OBSERVED (always) ---
        fo_ts = parse_temporal(finding.first_seen)
        if fo_ts is not None:
            events.append(_event(fid, TimelineEventType.FIRST_OBSERVED,
                                 fo_ts, conf, "confidence_graph", {}, idx))
            idx += 1

        # --- EMAIL: per-breach events ---
        if finding.type == FindingType.EMAIL:
            for breach in finding.metadata.get("breaches") or []:
                if not isinstance(breach, dict):
                    continue
                ts = parse_temporal(breach.get("BreachDate"))
                if ts is None:
                    continue
                name = breach.get("Name", "?")
                events.append(_event(fid, TimelineEventType.BREACH,
                                     ts, conf, "hibp",
                                     {"breach_name": name,
                                      "data_classes": breach.get("DataClasses", [])},
                                     idx))
                idx += 1
                if _PASSWORD_CLASSES & set(breach.get("DataClasses") or []):
                    events.append(_event(fid, TimelineEventType.BREACH_PASSWORD,
                                         ts, conf, "hibp",
                                         {"breach_name": name}, idx))
                    idx += 1

        # --- DOMAIN: registration event ---
        elif finding.type == FindingType.DOMAIN:
            ts = parse_temporal(finding.metadata.get("created_date"))
            if ts is not None:
                events.append(_event(fid, TimelineEventType.DOMAIN_REGISTERED,
                                     ts, conf, "whois", {}, idx))
                idx += 1

        # --- USERNAME / SOCIAL_ACTIVITY ---
        elif finding.type == FindingType.USERNAME:
            platform = finding.metadata.get("platform")
            if platform and fo_ts is not None:
                events.append(_event(fid, TimelineEventType.SOCIAL_ACTIVITY,
                                     fo_ts, conf,
                                     f"bios_{platform}",
                                     {"platform": platform}, idx))

    events.sort(key=lambda e: e.timestamp)
    return events
