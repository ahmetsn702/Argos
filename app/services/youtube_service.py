from typing import Dict
import httpx
from bs4 import BeautifulSoup
from app.utils.common import clean_text

async def fetch_bio_youtube(username: str, session=None) -> Dict[str, str]:
    try:
        async with httpx.AsyncClient(timeout=15, follow_redirects=True) as client:
            r = await client.get(f"https://www.youtube.com/@{username}")
        if r.status_code == 404:
            return {"platform": "YouTube", "url": f"https://www.youtube.com/@{username}", "status": "not_found",
                    "display_name": "", "bio": ""}
        s = BeautifulSoup(r.text, "html.parser")
        og_title = s.find("meta", property="og:title")
        og_desc  = s.find("meta", property="og:description")
        name = clean_text(og_title["content"]) if og_title and og_title.has_attr("content") else ""
        bio  = clean_text(og_desc["content"])  if og_desc  and og_desc.has_attr("content")  else ""
        status = "exists" if (bio or name) else "unknown"
        return {"platform": "YouTube", "url": f"https://www.youtube.com/@{username}", "status": status,
                "display_name": name, "bio": bio}
    except Exception:
        return {"platform": "YouTube", "url": f"https://www.youtube.com/@{username}", "status": "unknown",
                "display_name": "", "bio": ""}
