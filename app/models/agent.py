from pydantic import BaseModel, Field
from typing import Any, List, Optional
from datetime import datetime


class InvestigationRequest(BaseModel):
    seed: str
    goal: str
    max_iterations: int = 10
    timeout_seconds: int = 300


class ToolCall(BaseModel):
    tool_name: str
    params: dict
    result: dict
    iteration: int
    timestamp: str


class InvestigationReport(BaseModel):
    session_id: str
    seed: str
    goal: str
    tool_calls: List[ToolCall] = Field(default_factory=list)
    confidence: float = 0.0
    verdict: str = ""
    took_ms: int = 0
