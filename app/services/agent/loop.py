import asyncio
import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Optional

from app.models.agent import InvestigationReport, ToolCall
from app.services.agent.registry import ToolRegistry
from app.services.agent.budget import BudgetEnforcer
from app.services.agent.audit import AuditLogger

_LOW_CONFIDENCE_THRESHOLD = 0.6
_LOW_CONFIDENCE_CONSECUTIVE_LIMIT = 3


class InvestigationLoop:
    def __init__(
        self,
        registry: ToolRegistry,
        budget: BudgetEnforcer,
        audit: AuditLogger,
        max_iterations: int = 10,
    ):
        self.registry = registry
        self.budget = budget
        self.audit = audit
        self.max_iterations = max_iterations

    def _dedup_key(self, tool_name: str, params: dict) -> str:
        raw = json.dumps({"tool": tool_name, "params": params}, sort_keys=True)
        return hashlib.sha256(raw.encode()).hexdigest()

    def _update_confidence(
        self,
        current: float,
        tool_result: dict,
        iteration: int,
    ) -> float:
        if not tool_result.get("ok", False):
            return max(0.0, current - 0.05)
        data = tool_result.get("data")
        if data is None:
            return max(0.0, current - 0.02)
        # Increment confidence based on non-empty data
        increment = 0.1 + (0.05 * (1.0 - current))
        return min(1.0, current + increment)

    def _select_tool_round_robin(self, tools, iteration: int):
        if not tools:
            return None
        return tools[iteration % len(tools)]

    def _derive_verdict(self, confidence: float, tool_calls: list) -> str:
        if not tool_calls:
            return "No tools executed — insufficient data."
        successful = sum(1 for tc in tool_calls if tc.result.get("ok", False))
        total = len(tool_calls)
        if confidence >= 0.8:
            return f"High confidence ({confidence:.2f}). {successful}/{total} tool calls succeeded."
        if confidence >= 0.6:
            return f"Moderate confidence ({confidence:.2f}). {successful}/{total} tool calls succeeded."
        return f"Low confidence ({confidence:.2f}). Insufficient evidence from {total} tool calls."

    async def run(
        self,
        session_id: str,
        seed: str,
        goal: str,
        timeout_seconds: int = 300,
    ) -> InvestigationReport:
        start_ts = time.monotonic()
        start_wall = datetime.now(timezone.utc)

        tool_calls = []
        dedup_cache: dict = {}
        confidence = 0.0
        low_conf_streak = 0
        iteration = 0

        while iteration < self.max_iterations:
            # Deadline check
            elapsed = time.monotonic() - start_ts
            if elapsed >= timeout_seconds:
                break

            # Budget check
            available_tools = self.registry.list_available()
            if not available_tools:
                break

            tool = self._select_tool_round_robin(available_tools, iteration)
            if tool is None:
                break

            params = {"seed": seed, "goal": goal}

            # Dedup: same tool+args → use cached result
            key = self._dedup_key(tool.name, params)
            if key in dedup_cache:
                iteration += 1
                continue

            # Budget
            if not self.budget.check_and_consume(tool.name, session_id=session_id):
                break

            # Execute
            result = await tool.execute(params)
            dedup_cache[key] = result

            # Audit
            try:
                await self.audit.log_tool_call(session_id, tool.name, params, result)
            except Exception:
                pass

            timestamp = datetime.now(timezone.utc).isoformat()
            tc = ToolCall(
                tool_name=tool.name,
                params=params,
                result=result,
                iteration=iteration,
                timestamp=timestamp,
            )
            tool_calls.append(tc)

            # Update confidence
            prev_confidence = confidence
            confidence = self._update_confidence(confidence, result, iteration)

            # Low-confidence streak tracking
            if confidence < _LOW_CONFIDENCE_THRESHOLD:
                low_conf_streak += 1
            else:
                low_conf_streak = 0

            if low_conf_streak >= _LOW_CONFIDENCE_CONSECUTIVE_LIMIT:
                break

            iteration += 1

        took_ms = int((time.monotonic() - start_ts) * 1000)
        verdict = self._derive_verdict(confidence, tool_calls)

        return InvestigationReport(
            session_id=session_id,
            seed=seed,
            goal=goal,
            tool_calls=tool_calls,
            confidence=round(confidence, 4),
            verdict=verdict,
            took_ms=took_ms,
        )
