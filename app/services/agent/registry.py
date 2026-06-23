from app.services.agent.tools.base import BaseTool
from app.core.config import settings

class ToolRegistry:
    def __init__(self):
        self._tools = {}

    def register(self, tool: BaseTool):
        self._tools[tool.name] = tool

    def get(self, name: str):
        whitelist = [x.strip() for x in settings.AGENT_TOOL_WHITELIST.split(",") if x.strip()]
        if name not in whitelist:
            return None
        return self._tools.get(name)

    def list_available(self) -> list:
        whitelist = [x.strip() for x in settings.AGENT_TOOL_WHITELIST.split(",") if x.strip()]
        return [tool for name, tool in self._tools.items() if name in whitelist]

