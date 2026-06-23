from app.services.agent.tools.base import BaseTool
from app.services.agent.tools.client import get_client

class EmailOsintTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="email_osint",
            description="Perform email OSINT intelligence using Mosint."
        )

    async def _run(self, params: dict) -> dict:
        email = params.get("email")
        if not email:
            return {"ok": False, "data": None, "error": "Missing 'email' parameter"}
        
        smtp = params.get("smtp", 0)
        deep = params.get("deep", 0)
        timeout = params.get("timeout", 8.0)

        async with get_client() as client:
            response = await client.get(
                "/mosint/full",
                params={"email": email, "smtp": smtp, "deep": deep, "timeout": timeout}
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json(), "error": None}
            else:
                return {"ok": False, "data": None, "error": f"HTTP error {response.status_code}: {response.text}"}
