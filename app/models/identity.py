# app/models/identity.py
# -*- coding: utf-8 -*-
"""Canonical location for correlation/identity Pydantic models.

Re-exported by app/services/correlation/models.py for backward compatibility.
"""
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class EntityType(str, Enum):
    PERSON = "person"
    EMAIL = "email"
    PHONE = "phone"
    PROFILE = "profile"
    BREACH = "breach"
    DOMAIN = "domain"
    IP = "ip"
    FACE_CLUSTER = "face_cluster"


class Entity(BaseModel):
    type: EntityType
    value: str
    metadata: Dict[str, Any] = Field(default_factory=dict)

    def canonical_id(self) -> str:
        if self.type == EntityType.PROFILE and "platform" in self.metadata:
            return f"profile:{self.metadata['platform']}:{self.value}"
        return f"{self.type.value}:{self.value}"


class ProfileInput(BaseModel):
    platform: str
    username: str
    display_name: Optional[str] = None
    bio: Optional[str] = None
    profile_pic_url: Optional[str] = None


class IdentityMatch(BaseModel):
    entity_a: str
    entity_b: str
    confidence: float = Field(ge=0.0, le=1.0)
    verdict: str
    signals: Dict[str, float] = Field(default_factory=dict)
    evidence: List[str] = Field(default_factory=list)


class IdentityRequest(BaseModel):
    profiles: List[ProfileInput]


class IdentityResponse(BaseModel):
    matches: List[IdentityMatch]
    pairs_evaluated: int


class RiskBand(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Finding(BaseModel):
    category: str
    severity: str
    label: str
    evidence: List[str] = Field(default_factory=list)
    weight: int = 0


class RiskAssessment(BaseModel):
    score: int = Field(ge=0, le=100)
    band: RiskBand
    findings: List[Finding] = Field(default_factory=list)
    recommendations: List[str] = Field(default_factory=list)


class RiskRequest(BaseModel):
    mosint: Optional[Dict[str, Any]] = None
    darkweb: Optional[Dict[str, Any]] = None
    bios: Optional[Dict[str, Any]] = None
    phone: Optional[Dict[str, Any]] = None


class TimelineEvent(BaseModel):
    date: datetime
    event_type: str
    label: str
    source: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Timeline(BaseModel):
    events: List[TimelineEvent] = Field(default_factory=list)
    span_years: float = 0.0
    breach_clusters: List[Dict[str, Any]] = Field(default_factory=list)
    password_reuse_warnings: List[str] = Field(default_factory=list)


class TimelineRequest(BaseModel):
    mosint: Optional[Dict[str, Any]] = None
    domain: Optional[Dict[str, Any]] = None
    bios: Optional[Dict[str, Any]] = None
    extra_events: Optional[List[Dict[str, Any]]] = None


class GeoPoint(BaseModel):
    lat: float
    lng: float
    source: str
    confidence: float = 1.0
    label: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GeoCluster(BaseModel):
    points: List[GeoPoint] = Field(default_factory=list)
    centroids: List[Dict[str, Any]] = Field(default_factory=list)
    primary_region: Optional[str] = None


class GeoRequest(BaseModel):
    domain: Optional[Dict[str, Any]] = None
    exif: Optional[Dict[str, Any]] = None
    phone: Optional[Dict[str, Any]] = None
    extra_points: Optional[List[Dict[str, Any]]] = None
    cell_size_deg: float = Field(default=0.5, gt=0.0, le=10.0)


class GraphNode(BaseModel):
    id: str
    label: str
    group: str
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphEdge(BaseModel):
    source: str
    target: str
    label: Optional[str] = None
    edge_type: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class Graph(BaseModel):
    nodes: List[GraphNode] = Field(default_factory=list)
    edges: List[GraphEdge] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class GraphRequest(BaseModel):
    person: Optional[str] = None
    mosint: Optional[Dict[str, Any]] = None
    darkweb: Optional[Dict[str, Any]] = None
    bios: Optional[Dict[str, Any]] = None
    phone: Optional[Dict[str, Any]] = None
    domain: Optional[Dict[str, Any]] = None
    identity_matches: Optional[List[Dict[str, Any]]] = None
    geo_cluster: Optional[Dict[str, Any]] = None


class PivotSeed(BaseModel):
    email: Optional[str] = None
    username: Optional[str] = None
    phone: Optional[str] = None


class PivotResult(BaseModel):
    seed: PivotSeed
    discovered: List[Entity] = Field(default_factory=list)
    graph: Optional[Graph] = None
    truncated: bool = False
    depth_reached: int = 0
    took_ms: int = 0


class PivotRequest(BaseModel):
    seed: PivotSeed = Field(default_factory=PivotSeed)
    max_depth: int = Field(default=2, ge=1, le=3)
    max_entities_per_level: int = Field(default=20, ge=1, le=100)
    time_budget_seconds: float = Field(default=60.0, gt=0.0, le=180.0)
    include_graph: bool = True


class FullRequest(BaseModel):
    seed: PivotSeed = Field(default_factory=PivotSeed)
    include_identity: bool = True
    include_risk: bool = True
    include_timeline: bool = True
    include_geo: bool = True
    include_graph: bool = True
    include_pivot: bool = False
    pivot_max_depth: int = Field(default=2, ge=1, le=3)
    include_confidence: bool = False


class FullResponse(BaseModel):
    seed: PivotSeed
    raw_summary: Dict[str, bool] = Field(default_factory=dict)
    identity: Optional[IdentityResponse] = None
    risk: Optional[RiskAssessment] = None
    timeline: Optional[Timeline] = None
    geo: Optional[GeoCluster] = None
    graph: Optional[Dict[str, Any]] = None
    pivot: Optional[PivotResult] = None
    took_ms: int = 0
    confidence: Optional[Dict[str, Any]] = None


__all__ = [
    "EntityType", "Entity", "ProfileInput", "IdentityMatch",
    "IdentityRequest", "IdentityResponse", "RiskBand", "Finding",
    "RiskAssessment", "RiskRequest", "TimelineEvent", "Timeline",
    "TimelineRequest", "GeoPoint", "GeoCluster", "GeoRequest",
    "GraphNode", "GraphEdge", "Graph", "GraphRequest",
    "PivotSeed", "PivotResult", "PivotRequest", "FullRequest", "FullResponse",
]
