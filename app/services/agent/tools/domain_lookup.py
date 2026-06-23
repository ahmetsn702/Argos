from app.services.agent.tools.base import BaseTool
from app.services.agent.tools.client import get_client

class DomainLookupTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="domain_lookup",
            description="Perform domain or IP address OSINT lookup."
        )

    async def _run(self, params: dict) -> dict:
        target = params.get("target")
        if not target:
            return {"ok": False, "data": None, "error": "Missing 'target' parameter"}
        
        timeout = params.get("timeout", 10.0)

        async with get_client() as client:
            response = await client.get(
                "/domain/lookup",
                params={"target": target, "timeout": timeout}
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json(), "error": None}
            else:
                return {"ok": False, "data": None, "error": f"HTTP error {response.status_code}: {response.text}"}
