"""Pivot executor: runs expander strategies for a single finding value.

Responsibilities:
- Run all strategies for a FindingType in parallel (bounded by semaphore)
- Filter results by min_confidence
- Deduplicate by finding id
- Return list of ConfidenceFinding
"""

import asyncio
from typing import Callable, List

from app.models.confidence import ConfidenceFinding, FindingType
from app.services.pivot.strategy_map import strategies_for

_MAX_CONCURRENT = 5


async def execute_strategies(
    ftype: FindingType,
    value: str,
    min_confidence: float = 0.5,
    strategies: List[Callable] | None = None,
) -> List[ConfidenceFinding]:
    """Run all strategies for ftype on value, return deduplicated findings above threshold."""
    fns = strategies if strategies is not None else strategies_for(ftype)
    if not fns:
        return []

    sem = asyncio.Semaphore(_MAX_CONCURRENT)

    async def _run(fn: Callable) -> List[ConfidenceFinding]:
        async with sem:
            try:
                return await fn(value)
            except Exception:
                return []

    tasks = [asyncio.ensure_future(_run(fn)) for fn in fns]
    results = await asyncio.gather(*tasks)

    seen_ids: set = set()
    findings: List[ConfidenceFinding] = []
    for batch in results:
        for f in batch:
            if f.confidence_score < min_confidence:
                continue
            if f.id in seen_ids:
                continue
            seen_ids.add(f.id)
            findings.append(f)
    return findings
