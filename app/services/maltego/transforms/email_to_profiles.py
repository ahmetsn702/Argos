import app.services.agent.tools.client as agent_client

class EmailToProfiles:
    name = "argos.EmailToProfiles"
    display_name = "Email to Profiles"

    async def run(self, entity_value: str) -> list[dict]:
        async with agent_client.get_client() as client:
            response = await client.get("/mosint/full", params={"email": entity_value})
            if response.status_code != 200:
                return []
            data = response.json()
            results = []
            
            # Extract username prefix from email itself
            if "@" in entity_value:
                username = entity_value.split("@")[0]
                results.append({
                    "type": "maltego.Alias",
                    "value": username,
                    "properties": {"source": "email_prefix"}
                })
            
            # Gravatar username
            sources = data.get("sources", {})
            gravatar = sources.get("gravatar", {})
            if gravatar.get("exists") and gravatar.get("profile"):
                profile = gravatar["profile"]
                entry = profile.get("entry", [])
                if entry and isinstance(entry, list):
                    preferred = entry[0].get("preferredUsername")
                    if preferred:
                        results.append({
                            "type": "maltego.Alias",
                            "value": preferred,
                            "properties": {"source": "gravatar"}
                        })
            
            return results
