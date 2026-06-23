"""Person aggregator models."""

import hashlib
import json
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class PersonHints(BaseModel):
    usernames: List[str] = Field(default_factory=list)
    emails: List[str] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)


class PersonQuery(BaseModel):
    first_name: str
    last_name: str
    hometown: str
    hints: PersonHints = Field(default_factory=PersonHints)
    limit_per_source: int = 10
    timeout: int = 45
    fast: bool = True
    max_scans: Optional[int] = None

    def cache_key(self) -> str:
        key_dict = {
            "first": self.first_name,
            "last": self.last_name,
            "hometown": self.hometown,
            "hints": self.hints.model_dump(),
            "limit": self.limit_per_source,
            "fast": self.fast,
            "max_scans": self.max_scans,
        }
        raw = json.dumps(key_dict, ensure_ascii=False, sort_keys=True).encode("utf-8")
        return "person:" + hashlib.sha1(raw).hexdigest()


class SourceInfo(BaseModel):
    type: str
    ok: bool
    took_ms: int
    reason: Optional[str] = None
    meta: Dict[str, Any] = Field(default_factory=dict)


class ProfileEntry(BaseModel):
    platform: str
    handle: str
    url: str
    status: str = "unknown"
    confidence: float = 0.0
    evidence: List[str] = Field(default_factory=list)
    raw: Dict[str, Any] = Field(default_factory=dict)


class PersonCard(BaseModel):
    query: Dict[str, Any]
    summary: Dict[str, Any]
    profiles: List[ProfileEntry]
    emails: List[Dict[str, Any]] = Field(default_factory=list)
    phones: List[str] = Field(default_factory=list)
    images: List[str] = Field(default_factory=list)
    sources: List[SourceInfo] = Field(default_factory=list)
    verdict: str = "partial"
    took_ms: int = 0
