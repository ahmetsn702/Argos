import uuid
from typing import Any

from fastapi import APIRouter

import app.core.feature_flags as ff
from app.models.agent import InvestigationRequest, InvestigationReport
from app.services.agent.registry import ToolRegistry
from app.services.agent.budget import BudgetEnforcer
from app.services.agent.audit import AuditLogger
from app.services.agent.loop import InvestigationLoop
from app.services.agent.tools import (
    EmailOsintTool,
    PhoneLookupTool,
    SocialScanTool,
    DomainLookupTool,
    ConfidenceBuildTool,
    TemporalAnalyzeTool,
    PivotRunTool,
    GraphQueryTool,
)

router = APIRouter(prefix="/agent", tags=["agent"])

# Module-level singletons
_registry = ToolRegistry()
_budget = BudgetEnforcer()
_audit = AuditLogger()

# Register all tools
for _tool in [
    EmailOsintTool(),
    PhoneLookupTool(),
    SocialScanTool(),
    DomainLookupTool(),
    ConfidenceBuildTool(),
    TemporalAnalyzeTool(),
    PivotRunTool(),
    GraphQueryTool(),
]:
    _registry.register(_tool)

# In-memory session store  {session_id: InvestigationReport}
_session_store: dict = {}


@router.post("/investigate")
async def investigate(req: InvestigationRequest) -> Any:
    if not ff.AGENT_ENABLED:
        return {"enabled": False}

    session_id = str(uuid.uuid4())
    loop = InvestigationLoop(
        registry=_registry,
        budget=_budget,
        audit=_audit,
        max_iterations=req.max_iterations,
    )
    report = await loop.run(
        session_id=session_id,
        seed=req.seed,
        goal=req.goal,
        timeout_seconds=req.timeout_seconds,
    )
    _session_store[session_id] = report
    return report


@router.get("/sessions/{sid}")
async def get_session(sid: str) -> Any:
    if not ff.AGENT_ENABLED:
        return {"enabled": False}

    report = _session_store.get(sid)
    if report is None:
        return {"error": "session_not_found", "session_id": sid}
    return report


@router.get("/sessions/{sid}/audit")
async def get_session_audit(sid: str) -> Any:
    if not ff.AGENT_ENABLED:
        return {"enabled": False}

    logs = await _audit.get_logs(session_id=sid)
    return {"session_id": sid, "logs": logs}


@router.get("/budget/status")
async def budget_status() -> Any:
    if not ff.AGENT_ENABLED:
        return {"enabled": False}

    return {
        "daily_tool_calls_count": _budget.daily_tool_calls_count,
        "daily_spend_usd": _budget.daily_spend_usd,
        "last_reset_date": str(_budget.last_reset_date),
    }
