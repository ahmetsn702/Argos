import httpx
from urllib.parse import urlparse
from fastapi import APIRouter, Query
from app.core.config import API_KEY, CX, SAFE, LOCALE

router = APIRouter(tags=["search"])

# NOTE: The canonical `/combined-search` is served by `app.routers.media`,
# which fans out to text + reverse-image + intersection. This text-only
# variant is kept reachable at `/combined-search-v1` for callers that don't
# want to upload an image and only need the Google CSE text path.
@router.post("/combined-search-v1")
async def combined_search(name: str = Query(...), site: str | None = Query(None)):
    if not API_KEY or not CX:
        return {"search_name": name, "site_filter": site, "text_search_count": 0, "text_search_results": [], "image_search_count": 0, "image_search_results": []}
    query = f'\"{name}\"'
    params = {"key": API_KEY, "cx": CX, "q": query, "num": 10, "start": 1, "hl": LOCALE, "safe": SAFE}
    if site:
        params["siteSearch"] = site; params["siteSearchFilter"] = "i"
    try:
        async with httpx.AsyncClient(timeout=20) as client:
            r = await client.get("https://www.googleapis.com/customsearch/v1", params=params)
        items = r.json().get("items", []) or []
        results = [{"title": it.get("title"), "link": it.get("link"), "snippet": it.get("snippet"), "platform": urlparse(it.get("link","")).netloc} for it in items]
        return {"search_name": name, "site_filter": site, "text_search_count": len(results), "text_search_results": results, "image_search_count": 0, "image_search_results": []}
    except Exception:
        return {"search_name": name, "site_filter": site, "text_search_count": 0, "text_search_results": [], "image_search_count": 0, "image_search_results": []}
