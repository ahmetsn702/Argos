import app.services.agent.tools.client as agent_client

class UsernameToSocial:
    name = "argos.UsernameToSocial"
    display_name = "Username to Social Profiles"

    async def run(self, entity_value: str) -> list[dict]:
        async with agent_client.get_client() as client:
            response = await client.get("/username-scan", params={"username": entity_value})
            if response.status_code != 200:
                return []
            data = response.json()
            results = []
            for item in data.get("results", []):
                if item.get("status") == "exists":
                    results.append({
                        "type": "maltego.Alias",
                        "value": f"{item['platform']}:{entity_value}",
                        "properties": {
                            "platform": item["platform"],
                            "url": item["url"]
                        }
                    })
            return results
