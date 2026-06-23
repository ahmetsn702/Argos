from typing import Dict
import httpx
from app.utils.common import clean_text

async def fetch_bio_reddit(username: str, session=None) -> Dict[str, str]:
    try:
        headers = {"User-Agent": "reddit-bio/1.0"}
        async with httpx.AsyncClient(headers=headers, timeout=15, follow_redirects=True) as client:
            r = await client.get(f"https://www.reddit.com/user/{username}/about.json")
        if r.status_code == 404:
            return {"platform": "Reddit", "url": f"https://www.reddit.com/user/{username}/", "status": "not_found",
                    "display_name": "", "bio": ""}
        j = r.json()
        data = j.get("data") or {}
        sub = data.get("subreddit") or {}
        name = clean_text(sub.get("title", "") or data.get("name", "") or "")
        bio  = clean_text(sub.get("public_description", "") or sub.get("description", "") or "")
        status = "exists" if (bio or name) else "unknown"
        return {"platform": "Reddit", "url": f"https://www.reddit.com/user/{username}/", "status": status,
                "display_name": name, "bio": bio}
    except Exception:
        return {"platform": "Reddit", "url": f"https://www.reddit.com/user/{username}/", "status": "unknown",
                "display_name": "", "bio": ""}
