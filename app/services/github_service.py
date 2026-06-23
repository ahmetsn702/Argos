from typing import Dict
import httpx
from app.utils.common import clean_text

async def fetch_bio_github(username: str, session=None) -> Dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(f"https://api.github.com/users/{username}")
        if r.status_code == 404:
            return {"platform": "GitHub", "url": f"https://github.com/{username}", "status": "not_found",
                    "display_name": "", "bio": ""}
        j = r.json()
        name = clean_text(j.get("name") or "")
        bio  = clean_text(j.get("bio") or "")
        status = "exists" if (bio or name) else "unknown"
        return {"platform": "GitHub", "url": f"https://github.com/{username}", "status": status,
                "display_name": name, "bio": bio}
    except Exception:
        return {"platform": "GitHub", "url": f"https://github.com/{username}", "status": "unknown",
                "display_name": "", "bio": ""}
