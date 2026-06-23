# app/models/pivot.py
"""Pivot orchestrator models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PivotStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    TIMEOUT = "timeout"


class PivotStrategy(str, Enum):
    EMAIL = "email"
    PHONE = "phone"
    USERNAME = "username"
    DOMAIN = "domain"
    IP = "ip"
    FACE = "face"
    NAME = "name"


class PivotNode(BaseModel):
    finding_id: str
    finding_type: str
    value: str
    depth: int = Field(ge=0, le=4)
    confidence: float = Field(ge=0.0, le=1.0)
    parent_id: Optional[str] = None
    discovered_at: datetime
    modules_called: List[str] = Field(default_factory=list)


class PivotRunRequest(BaseModel):
    seed_finding_id: str
    seed_key: str
    max_depth: int = Field(default=2, ge=1, le=4)
    min_confidence: float = Field(default=0.5, ge=0.0, le=1.0)
    strategies: Optional[List[PivotStrategy]] = None
    dry_run: bool = False


class PivotSession(BaseModel):
    session_id: str
    seed_finding_id: str
    seed_key: str
    status: PivotStatus = PivotStatus.PENDING
    max_depth: int = Field(ge=1, le=4)
    nodes_discovered: List[PivotNode] = Field(default_factory=list)
    edges_created: int = 0
    started_at: datetime
    completed_at: Optional[datetime] = None
    took_ms: Optional[int] = None
    error: Optional[str] = None
    plan: Optional[List[Dict[str, Any]]] = None


__all__ = [
    "PivotStatus",
    "PivotStrategy",
    "PivotNode",
    "PivotRunRequest",
    "PivotSession",
]
