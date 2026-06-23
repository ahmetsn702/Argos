"""Pivot orchestrator: BFS expansion using confidence-aware executor.

Responsibilities:
- Create/manage PivotSession via session_store
- BFS expansion up to max_depth
- Convert findings to PivotNodes
- Track timing, handle errors/timeouts
- Respect dry_run (plan only, no execution)
"""

import asyncio
import time
import uuid
from datetime import datetime, timezone
from typing import Dict, List, Optional

from app.models.confidence import ConfidenceFinding, FindingType
from app.models.pivot import (
    PivotNode,
    PivotRunRequest,
    PivotSession,
    PivotStatus,
    PivotStrategy,
)
from app.services.pivot.executor import execute_strategies
from app.services.pivot.session_store import default_session_store

_TIMEOUT_SECONDS = 120.0

# PivotStrategy → FindingType mapping
_STRATEGY_TO_FTYPE: Dict[PivotStrategy, FindingType] = {
    PivotStrategy.EMAIL: FindingType.EMAIL,
    PivotStrategy.PHONE: FindingType.PHONE,
    PivotStrategy.USERNAME: FindingType.USERNAME,
    PivotStrategy.DOMAIN: FindingType.DOMAIN,
    PivotStrategy.IP: FindingType.IP,
    PivotStrategy.NAME: FindingType.NAME,
}


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _finding_to_node(
    finding: ConfidenceFinding, depth: int, parent_id: Optional[str] = None
) -> PivotNode:
    return PivotNode(
        finding_id=finding.id,
        finding_type=finding.type.value,
        value=finding.value,
        depth=depth,
        confidence=finding.confidence_score,
        parent_id=parent_id,
        discovered_at=_now(),
    )


def _infer_ftype(seed_key: str) -> FindingType:
    """Infer FindingType from seed_key format."""
    if "@" in seed_key:
        return FindingType.EMAIL
    if seed_key.startswith("+") or seed_key.replace("-", "").isdigit():
        return FindingType.PHONE
    return FindingType.USERNAME


def _allowed_ftypes(strategies: Optional[List[PivotStrategy]]) -> Optional[set]:
    """Return set of allowed FindingTypes, or None if all allowed."""
    if not strategies:
        return None
    return {_STRATEGY_TO_FTYPE[s] for s in strategies if s in _STRATEGY_TO_FTYPE}


async def run_pivot_session(request: PivotRunRequest) -> PivotSession:
    """Execute a full pivot session with BFS expansion."""
    session = default_session_store.create(
        seed_finding_id=request.seed_finding_id,
        seed_key=request.seed_key,
        max_depth=request.max_depth,
    )
    sid = session.session_id

    # Build plan
    seed_ftype = _infer_ftype(request.seed_key)
    allowed = _allowed_ftypes(request.strategies)
    plan = [{"depth": 0, "type": seed_ftype.value, "value": request.seed_key}]
    default_session_store.update_status(sid, PivotStatus.PENDING, plan=plan)

    if request.dry_run:
        default_session_store.mark_completed(sid, took_ms=0)
        return default_session_store.get(sid)  # type: ignore

    # Execute BFS
    default_session_store.update_status(sid, PivotStatus.RUNNING)
    start = time.monotonic()

    try:
        await _bfs_expand(
            sid=sid,
            seed_key=request.seed_key,
            seed_ftype=seed_ftype,
            max_depth=request.max_depth,
            min_confidence=request.min_confidence,
            allowed=allowed,
            deadline=start + _TIMEOUT_SECONDS,
        )
    except asyncio.TimeoutError:
        took = int((time.monotonic() - start) * 1000)
        default_session_store.mark_timeout(sid, took)
        return default_session_store.get(sid)  # type: ignore
    except Exception as e:
        default_session_store.mark_failed(sid, str(e))
        return default_session_store.get(sid)  # type: ignore

    took = int((time.monotonic() - start) * 1000)
    sess = default_session_store.get(sid)
    edges = max(0, len(sess.nodes_discovered) - 1) if sess else 0
    default_session_store.mark_completed(sid, took_ms=took, edges_created=edges)
    return default_session_store.get(sid)  # type: ignore


async def _bfs_expand(
    sid: str,
    seed_key: str,
    seed_ftype: FindingType,
    max_depth: int,
    min_confidence: float,
    allowed: Optional[set],
    deadline: float,
) -> None:
    """BFS: expand seed, then expand discovered findings up to max_depth."""
    seen_ids: set = set()
    # Queue items: (ftype, value, depth, parent_id)
    queue: List[tuple] = [(seed_ftype, seed_key, 1, None)]

    while queue:
        if time.monotonic() > deadline:
            raise asyncio.TimeoutError()

        next_queue: List[tuple] = []
        for ftype, value, depth, parent_id in queue:
            if allowed and ftype not in allowed:
                continue
            if time.monotonic() > deadline:
                raise asyncio.TimeoutError()

            findings = await execute_strategies(ftype, value, min_confidence)
            for f in findings:
                if f.id in seen_ids:
                    continue
                seen_ids.add(f.id)
                node = _finding_to_node(f, depth, parent_id)
                default_session_store.add_node(sid, node)
                if depth < max_depth:
                    next_queue.append((f.type, f.value, depth + 1, f.id))

        queue = next_queue
