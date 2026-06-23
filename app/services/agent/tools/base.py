from abc import ABC, abstractmethod
import app.core.feature_flags as ff

class BaseTool(ABC):
    def __init__(self, name: str, description: str):
        self.name = name
        self.description = description

    async def execute(self, params: dict) -> dict:
        if not ff.AGENT_ENABLED:
            return {"ok": False, "data": None, "error": "agent_disabled"}
        try:
            return await self._run(params)
        except Exception as e:
            return {"ok": False, "data": None, "error": str(e)}

    @abstractmethod
    async def _run(self, params: dict) -> dict:
        pass
