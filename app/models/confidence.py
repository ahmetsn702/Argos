# app/models/confidence.py
"""Confidence Graph data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


class FindingType(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    NAME = "name"
    LOCATION = "location"
    IP = "ip"
    DOMAIN = "domain"


class EdgeType(str, Enum):
    SAME_AS = "same_as"
    SUPPORTS = "supports"
    CONTRADICTS = "contradicts"
    DERIVED_FROM = "derived_from"


class SourceKind(str, Enum):
    BREACH = "breach"
    PHONE_VERIFIED = "phone_verified"
    WHOIS = "whois"
    SOCIAL_VERIFIED = "social_verified"
    SOCIAL = "social"
    SCRAPING = "scraping"
    AI = "ai"


class SourceObservation(BaseModel):
    source_id: str
    source_kind: SourceKind
    weight: float = Field(ge=0.0, le=1.0)
    observed_at: datetime
    evidence_ref: Optional[str] = None
    contradicts: List[str] = Field(default_factory=list)


class ConfidenceFinding(BaseModel):
    id: str
    type: FindingType
    value: str
    raw_value: str
    sources: List[SourceObservation] = Field(default_factory=list)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    first_seen: datetime
    last_seen: datetime
    corroborated_by: List[str] = Field(default_factory=list)
    contradicted_by: List[str] = Field(default_factory=list)
    derived_from: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ConfidenceEdge(BaseModel):
    source_id: str
    target_id: str
    edge_type: EdgeType
    weight: float = Field(ge=0.0, le=1.0)
    metadata: Dict[str, Any] = Field(default_factory=dict)

    @field_validator("target_id")
    @classmethod
    def no_self_loop(cls, v: str, info) -> str:
        if info.data.get("source_id") == v:
            raise ValueError("source_id and target_id must differ")
        return v


class ConfidenceGraph(BaseModel):
    seed_key: str
    findings: Dict[str, ConfidenceFinding] = Field(default_factory=dict)
    edges: List[ConfidenceEdge] = Field(default_factory=list)
    computed_at: datetime
    version: int = 1
    metadata: Dict[str, Any] = Field(default_factory=dict)


__all__ = [
    "FindingType", "EdgeType", "SourceKind",
    "SourceObservation", "ConfidenceFinding", "ConfidenceEdge", "ConfidenceGraph",
]
