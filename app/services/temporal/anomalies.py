"""Temporal anomaly detectors.

Four detectors, each returning a list of AnomalyFlag:
  detect_night_activity       — events between local NIGHT_START_HOUR..NIGHT_END_HOUR
  detect_coordinated_creation — same UTC date, ≥ BURST_MIN_PLATFORMS distinct platforms
  detect_silence_then_burst   — gap ≥ SILENCE_DAYS followed by ≥ 3 events in 7 days
  detect_breach_activity_overlap — non-breach events within ±BREACH_OVERLAP_DAYS of a breach

Severity uses intensity scales (count-based thresholds from constants).
detect_all() runs all four and concatenates results.
"""

import uuid
from datetime import timedelta
from typing import List

from app.models.temporal import AnomalyFlag, AnomalySeverity, AnomalyType, TimelineEvent, TimelineEventType
from app.services.temporal import constants
from app.services.temporal.parsing import is_night


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _flag(atype: AnomalyType, severity: AnomalySeverity,
          event_ids: List[str], explanation: str, **meta) -> AnomalyFlag:
    return AnomalyFlag(
        anomaly_id=uuid.uuid4().hex[:12],
        type=atype,
        severity=severity,
        event_ids=event_ids,
        explanation=explanation,
        metadata=meta,
    )


def _severity_by_count(n: int, low: int, med: int, high: int) -> AnomalySeverity:
    if n >= high:
        return AnomalySeverity.HIGH
    if n >= med:
        return AnomalySeverity.MEDIUM
    return AnomalySeverity.LOW


# ---------------------------------------------------------------------------
# 1. Night activity
# ---------------------------------------------------------------------------

def detect_night_activity(events: List[TimelineEvent]) -> List[AnomalyFlag]:
    offset = constants.NIGHT_TZ_OFFSET
    start = constants.NIGHT_START_HOUR
    end = constants.NIGHT_END_HOUR
    night = [e for e in events if is_night(e.timestamp, offset, start, end)]
    if len(night) < constants.NIGHT_LOW_EVENTS:
        return []
    n = len(night)
    severity = _severity_by_count(
        n, constants.NIGHT_LOW_EVENTS, constants.NIGHT_MED_EVENTS, constants.NIGHT_HIGH_EVENTS
    )
    ids = [e.event_id for e in night]
    ts_range = f"{night[0].timestamp.date()}..{night[-1].timestamp.date()}"
    return [_flag(
        AnomalyType.NIGHT_ACTIVITY, severity, ids,
        f"Gece aktivitesi tespit edildi: {n} olay {ts_range} tarih aralığında "
        f"(yerel {start:02d}:00-{end:02d}:00).",
        event_count=n,
    )]


# ---------------------------------------------------------------------------
# 2. Coordinated creation (same UTC date, distinct platforms)
# ---------------------------------------------------------------------------

def detect_coordinated_creation(events: List[TimelineEvent]) -> List[AnomalyFlag]:
    social_types = {TimelineEventType.SOCIAL_ACTIVITY, TimelineEventType.ACCOUNT_CREATED}
    social = [e for e in events if e.event_type in social_types]

    # group by UTC date
    by_date: dict = {}
    for e in social:
        day = e.timestamp.date()
        by_date.setdefault(day, []).append(e)

    flags = []
    for day, day_events in by_date.items():
        platforms = {e.metadata.get("platform") for e in day_events
                     if e.metadata.get("platform")}
        n = len(platforms)
        if n < constants.BURST_MIN_PLATFORMS:
            continue
        severity = _severity_by_count(
            n, constants.BURST_MIN_PLATFORMS,
            constants.BURST_MED_PLATFORMS, constants.BURST_HIGH_PLATFORMS
        )
        ids = [e.event_id for e in day_events]
        flags.append(_flag(
            AnomalyType.COORDINATED_CREATION, severity, ids,
            f"Koordineli hesap oluşturma: {day} tarihinde {n} farklı platformda aktivite.",
            date=str(day), platform_count=n,
        ))
    return flags


# ---------------------------------------------------------------------------
# 3. Silence then burst
# ---------------------------------------------------------------------------

def detect_silence_then_burst(events: List[TimelineEvent]) -> List[AnomalyFlag]:
    if len(events) < 2:
        return []
    sorted_ev = sorted(events, key=lambda e: e.timestamp)
    silence_days = constants.SILENCE_DAYS
    burst_window = timedelta(days=7)
    flags = []

    for i in range(1, len(sorted_ev)):
        gap = (sorted_ev[i].timestamp - sorted_ev[i - 1].timestamp).days
        if gap < silence_days:
            continue
        # count events within 7 days after sorted_ev[i]
        burst_start = sorted_ev[i].timestamp
        burst_end = burst_start + burst_window
        burst = [e for e in sorted_ev[i:] if burst_start <= e.timestamp <= burst_end]
        n = len(burst)
        if n < 3:
            continue
        severity = _severity_by_count(
            n, 3, constants.BURST_MED_PLATFORMS, constants.BURST_HIGH_PLATFORMS
        )
        ids = [e.event_id for e in burst]
        flags.append(_flag(
            AnomalyType.SILENCE_THEN_BURST, severity, ids,
            f"Uzun sessizlik sonrası ani aktivite: {gap} günlük boşluktan sonra "
            f"7 gün içinde {n} olay.",
            silence_days=gap, burst_count=n,
        ))
    return flags


# ---------------------------------------------------------------------------
# 4. Breach activity overlap
# ---------------------------------------------------------------------------

def detect_breach_activity_overlap(events: List[TimelineEvent]) -> List[AnomalyFlag]:
    breach_types = {TimelineEventType.BREACH, TimelineEventType.BREACH_PASSWORD}
    breach_events = [e for e in events if e.event_type in breach_types]
    non_breach = [e for e in events if e.event_type not in breach_types]
    if not breach_events or not non_breach:
        return []

    window = timedelta(days=constants.BREACH_OVERLAP_DAYS)
    flags = []
    for breach in breach_events:
        nearby = [
            e for e in non_breach
            if abs((e.timestamp - breach.timestamp).total_seconds()) <= window.total_seconds()
        ]
        n = len(nearby)
        if n < 2:
            continue
        severity = _severity_by_count(n, 2, 5, 10)
        ids = [breach.event_id] + [e.event_id for e in nearby]
        flags.append(_flag(
            AnomalyType.BREACH_ACTIVITY_OVERLAP, severity, ids,
            f"İhlal-aktivite örtüşmesi: {breach.metadata.get('breach_name', '?')} "
            f"ihlali etrafında ±{constants.BREACH_OVERLAP_DAYS} gün içinde {n} aktivite.",
            breach_event_id=breach.event_id, nearby_count=n,
        ))
    return flags


# ---------------------------------------------------------------------------
# detect_all
# ---------------------------------------------------------------------------

def detect_all(events: List[TimelineEvent]) -> List[AnomalyFlag]:
    flags: List[AnomalyFlag] = []
    flags.extend(detect_night_activity(events))
    flags.extend(detect_coordinated_creation(events))
    flags.extend(detect_silence_then_burst(events))
    flags.extend(detect_breach_activity_overlap(events))
    return flags
