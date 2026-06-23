from pydantic import BaseModel
from typing import Optional


class WatchlistTarget(BaseModel):
    id: Optional[int] = None
    type: str  # e.g., "email", "username", "domain"
    value: str  # e.g., "test@example.com", "john_doe"
    description: Optional[str] = None
    status: str = "active"  # "active", "paused"
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    last_run: Optional[str] = None


class WatchlistChange(BaseModel):
    id: Optional[int] = None
    target_id: int
    change_type: str  # e.g., "created", "updated", "deleted", "scan_run"
    description: str
    timestamp: str


class WatchlistAlert(BaseModel):
    id: Optional[int] = None
    target_id: int
    title: str
    severity: str  # "low", "medium", "high", "critical"
    message: str
    timestamp: str
    is_read: bool = False
