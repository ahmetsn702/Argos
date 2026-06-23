import app.services.agent.tools.client as agent_client

class PhoneToIdentity:
    name = "argos.PhoneToIdentity"
    display_name = "Phone to Identity/Location"

    async def run(self, entity_value: str) -> list[dict]:
        async with agent_client.get_client() as client:
            response = await client.get("/phone/lookup", params={"number": entity_value})
            if response.status_code != 200:
                return []
            data = response.json()
            results = []
            
            # Extract carrier
            carrier = data.get("carrier")
            if carrier:
                results.append({
                    "type": "maltego.Unknown",
                    "value": carrier,
                    "properties": {"type": "carrier"}
                })
            
            # Extract country
            country = data.get("country")
            if country:
                results.append({
                    "type": "maltego.Location",
                    "value": country,
                    "properties": {"type": "country"}
                })
                
            # Extract location
            location = data.get("location")
            if location and location != country:
                results.append({
                    "type": "maltego.Location",
                    "value": location,
                    "properties": {"type": "city_region"}
                })
                
            # Extract name/identity if present
            name = data.get("name")
            if name:
                results.append({
                    "type": "maltego.Person",
                    "value": name,
                    "properties": {"type": "owner_name"}
                })
                
            return results
