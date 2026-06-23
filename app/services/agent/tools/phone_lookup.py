from app.services.agent.tools.base import BaseTool
from app.services.agent.tools.client import get_client

class PhoneLookupTool(BaseTool):
    def __init__(self):
        super().__init__(
            name="phone_lookup",
            description="Perform phone number lookup intelligence."
        )

    async def _run(self, params: dict) -> dict:
        number = params.get("number")
        if not number:
            return {"ok": False, "data": None, "error": "Missing 'number' parameter"}
        
        timeout = params.get("timeout", 10.0)

        async with get_client() as client:
            response = await client.get(
                "/phone/lookup",
                params={"number": number, "timeout": timeout}
            )
            if response.status_code == 200:
                return {"ok": True, "data": response.json(), "error": None}
            else:
                return {"ok": False, "data": None, "error": f"HTTP error {response.status_code}: {response.text}"}
