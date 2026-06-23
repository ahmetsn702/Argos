"""Pivot orchestrator API endpoints."""

from typing import List

from fastapi import APIRouter, HTTPException, Query

from app.models.pivot import PivotRunRequest, PivotSession
from app.services.pivot.orchestrator import run_pivot_session
from app.services.pivot.session_store import default_session_store

router = APIRouter(prefix="/pivot", tags=["pivot"])


@router.post("/run", response_model=PivotSession)
async def pivot_run(req: PivotRunRequest):
    try:
        return await run_pivot_session(req)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/session/{session_id}", response_model=PivotSession)
def pivot_session(session_id: str):
    session = default_session_store.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.get("/history", response_model=List[PivotSession])
def pivot_history(limit: int = Query(default=20, ge=1, le=100)):
    return default_session_store.history(limit)
