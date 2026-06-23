"""LLM analysis models."""

from typing import Optional

from pydantic import BaseModel


class OsintAnalysisRequest(BaseModel):
    data: dict
    context: Optional[str] = None
