# app/services/pivot/adapters.py
"""Bridge: legacy correlation Entity model → ConfidenceFinding.

Used by the orchestrator's hybrid path to translate the output of the
existing ``correlation.pivot_engine.run_pivot()`` motor (which returns
``Entity`` objects) into Confidence Graph findings.
"""

from datetime import datetime, timezone
from typing import Optional

from app.models.confidence import (
    ConfidenceFinding,
    FindingType,
    SourceKind,
    SourceObservation,
)
from app.models.identity import Entity, EntityType
from app.services.confidence.normalizers import (
    canonical_id,
    normalize_domain,
    normalize_email,
    normalize_name,
    normalize_phone,
    normalize_username,
)

# EntityType → FindingType. BREACH and FACE_CLUSTER are intentionally
# absent (no canonical FindingType yet).
_TYPE_MAP = {
    EntityType.EMAIL: FindingType.EMAIL,
    EntityType.PHONE: FindingType.PHONE,
    EntityType.PROFILE: FindingType.USERNAME,
    EntityType.DOMAIN: FindingType.DOMAIN,
    EntityType.IP: FindingType.IP,
    EntityType.PERSON: FindingType.NAME,
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _normalize_for_type(ftype: FindingType, raw: str) -> str:
    if ftype == FindingType.EMAIL:
        return normalize_email(raw)
    if ftype == FindingType.PHONE:
        return normalize_phone(raw)
    if ftype == FindingType.USERNAME:
        return normalize_username(raw)
    if ftype == FindingType.DOMAIN:
        return normalize_domain(raw)
    if ftype == FindingType.NAME:
        return normalize_name(raw)
    if ftype == FindingType.IP:
        return raw.strip()
    return raw


def entity_to_finding(
    entity: Entity,
    source_id: str = "pivot_legacy",
    source_kind: SourceKind = SourceKind.SCRAPING,
    weight: float = 0.40,
) -> Optional[ConfidenceFinding]:
    """Translate a legacy Entity into a ConfidenceFinding.

    Returns ``None`` for entity types that have no corresponding
    FindingType (e.g. BREACH, FACE_CLUSTER).
    """
    ftype = _TYPE_MAP.get(entity.type)
    if ftype is None:
        return None

    raw_value = str(entity.value)
    try:
        normalized = _normalize_for_type(ftype, raw_value)
    except Exception:
        return None

    cid = canonical_id(ftype, normalized)
    obs = SourceObservation(
        source_id=source_id,
        source_kind=source_kind,
        weight=weight,
        observed_at=_now(),
    )
    now = _now()
    metadata = dict(entity.metadata) if entity.metadata else {}
    return ConfidenceFinding(
        id=cid,
        type=ftype,
        value=normalized,
        raw_value=raw_value,
        sources=[obs],
        confidence_score=weight,
        first_seen=now,
        last_seen=now,
        metadata=metadata,
    )
