"""Geo OSINT models."""

from pydantic import BaseModel


class GeoResult(BaseModel):
    source: str
    lat: float | None = None
    lng: float | None = None
    confidence: float = 0.0
    radius_km: int = 0
    country: str | None = None
    region: str | None = None
    reasoning: dict = {}
    fallback: bool = False
