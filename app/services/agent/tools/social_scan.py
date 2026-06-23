from app.services.agent.tools.base import BaseTool
from app.services.agent.tools.client import get_client

class SocialScanTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="social_scan",
            description="Scan social media platforms for a specific username."
        )

    async def _run(self, params: dict) -> dict:
        username = params.get("username")
        if not username:
            return {"ok": False, "data": None, "error": "Missing 'username' parameter"}
        
        only = params.get("only")

        queryParams = {"username": username}
        if only is not None:
            queryParams["only"] = only

        async with get_client() as client:
            response = await client.get(
                "/username-scan",
                params=queryParams
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json(), "error": None}
            else:
                return {"ok": False, "data": None, "error": f"HTTP error {response.status_code}: {response.text}"}
