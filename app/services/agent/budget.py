import threading
from datetime import datetime, timezone
from app.core.config import settings

class BudgetEnforcer:
    def __init__(self):
        self.lock = threading.Lock()
        self.daily_tool_calls_count = 0
        self.daily_spend_usd = 0.0
        self.session_calls_count = {}
        self.last_reset_date = datetime.now(timezone.utc).date()
        self.tool_costs = {
            "email_osint": 0.50,
            "phone_lookup": 0.20,
            "social_scan": 0.10,
            "domain_lookup": 0.05,
            "confidence_build": 0.05,
            "temporal_analyze": 0.10,
            "pivot_run": 0.25,
            "graph_query": 0.15,
        }

    def _check_reset(self):
        now_date = datetime.now(timezone.utc).date()
        if now_date > self.last_reset_date:
            self.daily_tool_calls_count = 0
            self.daily_spend_usd = 0.0
            self.session_calls_count.clear()
            self.last_reset_date = now_date

    def check_and_consume(self, tool_name: str, session_id: str = None, cost: float = None) -> bool:
        with self.lock:
            self._check_reset()
            
            if cost is None:
                cost = self.tool_costs.get(tool_name, 0.05)

            # Check daily quota
            daily_limit = settings.AGENT_DAILY_TOOL_QUOTA
            if self.daily_tool_calls_count >= daily_limit:
                return False

            # Check daily budget
            budget_limit = settings.AGENT_DAILY_BUDGET_USD
            if self.daily_spend_usd + cost > budget_limit:
                return False

            # Check session limit if session_id is provided
            if session_id:
                session_limit = settings.AGENT_SESSION_MAX_TOOL_CALLS
                current_session_calls = self.session_calls_count.get(session_id, 0)
                if current_session_calls >= session_limit:
                    return False

            # Consume
            self.daily_tool_calls_count += 1
            self.daily_spend_usd += cost
            if session_id:
                self.session_calls_count[session_id] = self.session_calls_count.get(session_id, 0) + 1
            return True
