import app.services.agent.tools.client as agent_client

class IpToGeo:
    name = "argos.IpToGeo"
    display_name = "IP to Geo Location"

    async def run(self, entity_value: str) -> list[dict]:
        async with agent_client.get_client() as client:
            response = await client.get("/domain/lookup", params={"target": entity_value})
            if response.status_code != 200:
                return []
            data = response.json()
            geo = data.get("geo", {})
            results = []
            
            country = geo.get("country")
            city = geo.get("city")
            region = geo.get("region")
            isp = geo.get("isp")
            
            loc_parts = []
            if city:
                loc_parts.append(city)
            if region:
                loc_parts.append(region)
            if country:
                loc_parts.append(country)
                
            if loc_parts:
                full_loc = ", ".join(loc_parts)
                results.append({
                    "type": "maltego.Location",
                    "value": full_loc,
                    "properties": {
                        "city": city or "",
                        "region": region or "",
                        "country": country or "",
                        "lat": str(geo.get("lat") or ""),
                        "lng": str(geo.get("lng") or "")
                    }
                })
            elif country:
                results.append({
                    "type": "maltego.Location",
                    "value": country,
                    "properties": {
                        "country": country,
                        "lat": str(geo.get("lat") or ""),
                        "lng": str(geo.get("lng") or "")
                    }
                })
                
            if isp:
                results.append({
                    "type": "maltego.Unknown",
                    "value": isp,
                    "properties": {"type": "isp"}
                })
                
            return results
