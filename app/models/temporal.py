"""Temporal Intelligence data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class TimelineEventType(str, Enum):
    BREACH = "breach"
    BREACH_PASSWORD = "breach_password"
    DOMAIN_REGISTERED = "domain_registered"
    FIRST_OBSERVED = "first_observed"
    LAST_OBSERVED = "last_observed"
    SOCIAL_ACTIVITY = "social_activity"
    ACCOUNT_CREATED = "account_created"
    OTHER = "other"


class AnomalyType(str, Enum):
    NIGHT_ACTIVITY = "night_activity"
    COORDINATED_CREATION = "coordinated_creation"
    SILENCE_THEN_BURST = "silence_then_burst"
    BREACH_ACTIVITY_OVERLAP = "breach_activity_overlap"


class AnomalySeverity(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TimelineEvent(BaseModel):
    event_id: str
    finding_id: str
    event_type: TimelineEventType
    timestamp: datetime
    confidence: float = Field(ge=0.0, le=1.0)
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TimelineCluster(BaseModel):
    cluster_id: str
    start: datetime
    end: datetime
    span_minutes: int
    event_ids: List[str]
    event_types: List[TimelineEventType]


class AnomalyFlag(BaseModel):
    anomaly_id: str
    type: AnomalyType
    severity: AnomalySeverity
    event_ids: List[str]
    explanation: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class TemporalNarrative(BaseModel):
    summary: str
    risk_level: str
    key_observations: List[str]
    model: str
    generated_at: datetime


class TemporalAnalysis(BaseModel):
    seed_key: str
    events: List[TimelineEvent] = Field(default_factory=list)
    clusters: List[TimelineCluster] = Field(default_factory=list)
    anomalies: List[AnomalyFlag] = Field(default_factory=list)
    narrative: Optional[TemporalNarrative] = None
    computed_at: datetime
    metadata: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "TimelineEventType", "AnomalyType", "AnomalySeverity",
    "TimelineEvent", "TimelineCluster", "AnomalyFlag",
    "TemporalNarrative", "TemporalAnalysis",
]
