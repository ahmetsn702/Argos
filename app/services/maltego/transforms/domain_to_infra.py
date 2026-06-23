import app.services.agent.tools.client as agent_client

class DomainToInfra:
    name = "argos.DomainToInfra"
    display_name = "Domain to Infrastructure"

    async def run(self, entity_value: str) -> list[dict]:
        async with agent_client.get_client() as client:
            response = await client.get("/domain/lookup", params={"target": entity_value})
            if response.status_code != 200:
                return []
            data = response.json()
            results = []
            
            # IP Address
            ip = data.get("ip")
            if ip:
                results.append({
                    "type": "maltego.IPv4Address",
                    "value": ip,
                    "properties": {"type": "resolved_ip"}
                })
                
            # DNS records: MX, NS
            dns = data.get("dns", {})
            records = dns.get("records", {})
            
            for ns in records.get("NS", []):
                if ns:
                    results.append({
                        "type": "maltego.Domain",
                        "value": ns.rstrip("."),
                        "properties": {"type": "nameserver"}
                    })
                    
            for mx in records.get("MX", []):
                if mx:
                    parts = mx.split()
                    host = parts[-1] if parts else mx
                    host = host.rstrip(".")
                    results.append({
                        "type": "maltego.Domain",
                        "value": host,
                        "properties": {"type": "mailserver"}
                    })
                    
            return results
