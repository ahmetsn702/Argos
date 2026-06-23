from app.services.agent.tools.base import BaseTool
from app.services.agent.tools.client import get_client

class ConfidenceBuildTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="confidence_build",
            description="Build or merge a confidence graph for a seed key."
        )

    async def _run(self, params: dict) -> dict:
        seed_key = params.get("seed_key")
        if not seed_key:
            return {"ok": False, "data": None, "error": "Missing 'seed_key' parameter"}
        
        raw = params.get("raw", {})
        ttl_hours = params.get("ttl_hours")

        payload = {"seed_key": seed_key, "raw": raw}
        if ttl_hours is not None:
            payload["ttl_hours"] = ttl_hours

        async with get_client() as client:
            response = await client.post(
                "/confidence/build",
                json=payload
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json(), "error": None}
            else:
                return {"ok": False, "data": None, "error": f"HTTP error {response.status_code}: {response.text}"}
