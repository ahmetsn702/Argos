from app.services.agent.tools.base import BaseTool
from app.services.agent.tools.client import get_client

class TemporalAnalyzeTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="temporal_analyze",
            description="Perform temporal intelligence timeline anomaly analysis on a seed key."
        )

    async def _run(self, params: dict) -> dict:
        seed_key = params.get("seed_key")
        if not seed_key:
            return {"ok": False, "data": None, "error": "Missing 'seed_key' parameter"}
        
        narrative = params.get("narrative", False)
        force = params.get("force", False)

        payload = {"seed_key": seed_key, "narrative": narrative, "force": force}

        async with get_client() as client:
            response = await client.post(
                "/temporal/analyze",
                json=payload
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json(), "error": None}
            else:
                return {"ok": False, "data": None, "error": f"HTTP error {response.status_code}: {response.text}"}
