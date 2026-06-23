"""Temporal Intelligence API endpoints."""

import threading
import time
from typing import Any, Dict

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.models.temporal import TemporalAnalysis
from app.services.temporal.cache import default_temporal_cache
from app.services.temporal.service import analyze

router = APIRouter(prefix="/temporal", tags=["temporal"])

_rate_store: Dict[str, list] = {}
_rate_lock = threading.Lock()


def _check_rate_limit(key: str, max_calls: int, window_seconds: int = 60) -> bool:
    now = time.time()
    with _rate_lock:
        calls = [t for t in _rate_store.get(key, []) if now - t < window_seconds]
        if len(calls) >= max_calls:
            _rate_store[key] = calls
            return True
        calls.append(now)
        _rate_store[key] = calls
        return False


class AnalyzeRequest(BaseModel):
    seed_key: str
    narrative: bool = False
    force: bool = False


@router.post("/analyze", response_model=TemporalAnalysis)
async def temporal_analyze(req: AnalyzeRequest):
    if _check_rate_limit(f"analyze:{req.seed_key}", max_calls=5):
        raise HTTPException(status_code=429, detail="Rate limit: 5 calls/minute")
    result = await analyze(req.seed_key, narrative=req.narrative, force=req.force)
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f"Confidence graph not found for seed_key: {req.seed_key}")
    return result


@router.get("/timeline/{seed_key}", response_model=TemporalAnalysis)
def temporal_timeline(seed_key: str):
    result = default_temporal_cache.get(seed_key)
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f"No cached timeline for seed_key: {seed_key}")
    return result


@router.get("/anomalies/{seed_key}")
def temporal_anomalies(seed_key: str) -> Dict[str, Any]:
    result = default_temporal_cache.get(seed_key)
    if result is None:
        raise HTTPException(status_code=404,
                            detail=f"No cached analysis for seed_key: {seed_key}")
    by_type: Dict[str, int] = {}
    by_severity: Dict[str, int] = {}
    for flag in result.anomalies:
        by_type[flag.type.value] = by_type.get(flag.type.value, 0) + 1
        by_severity[flag.severity.value] = by_severity.get(flag.severity.value, 0) + 1
    return {
        "seed_key": seed_key,
        "anomalies": [f.model_dump() for f in result.anomalies],
        "stats": {
            "total": len(result.anomalies),
            "by_type": by_type,
            "by_severity": by_severity,
        },
    }
