from app.services.agent.tools.base import BaseTool
from app.services.agent.tools.client import get_client

class PivotRunTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="pivot_run",
            description="Run a pivot session to discover related entities in the intelligence graph."
        )

    async def _run(self, params: dict) -> dict:
        seed_finding_id = params.get("seed_finding_id")
        seed_key = params.get("seed_key")
        if not seed_finding_id or not seed_key:
            return {"ok": False, "data": None, "error": "Missing 'seed_finding_id' or 'seed_key' parameter"}
        
        max_depth = params.get("max_depth", 2)
        min_confidence = params.get("min_confidence", 0.5)
        strategies = params.get("strategies")
        dry_run = params.get("dry_run", False)

        payload = {
            "seed_finding_id": seed_finding_id,
            "seed_key": seed_key,
            "max_depth": max_depth,
            "min_confidence": min_confidence,
            "dry_run": dry_run
        }
        if strategies is not None:
            payload["strategies"] = strategies

        async with get_client() as client:
            response = await client.post(
                "/pivot/run",
                json=payload
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json(), "error": None}
            else:
                return {"ok": False, "data": None, "error": f"HTTP error {response.status_code}: {response.text}"}
