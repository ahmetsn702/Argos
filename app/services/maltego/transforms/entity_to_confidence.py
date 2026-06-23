import app.services.agent.tools.client as agent_client
from app.services.maltego.entity_map import get_entity_type

class EntityToConfidence:
    name = "argos.EntityToConfidence"
    display_name = "Entity to Confidence Findings"

    async def run(self, entity_value: str) -> list[dict]:
        async with agent_client.get_client() as client:
            response = await client.get("/confidence/graph", params={"seed_key": entity_value})
            
            if response.status_code == 404:
                build_resp = await client.post("/confidence/build", json={"seed_key": entity_value, "raw": {}})
                if build_resp.status_code == 200:
                    data = build_resp.json()
                else:
                    return []
            elif response.status_code == 200:
                data = response.json()
            else:
                return []
                
            results = []
            findings = data.get("findings", {})
            if isinstance(findings, dict):
                for fid, f in findings.items():
                    results.append({
                        "type": get_entity_type(f.get("type")),
                        "value": f.get("value"),
                        "properties": {
                            "confidence_score": str(f.get("confidence_score", 1.0)),
                            "finding_id": f.get("id")
                        }
                    })
            return results
