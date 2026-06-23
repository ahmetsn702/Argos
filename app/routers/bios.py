import asyncio
import inspect
from typing import Optional, Dict, List
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.services.x_fetch import XService
from app.services.github_service import fetch_bio_github
from app.services.reddit_service import fetch_bio_reddit
from app.services.youtube_service import fetch_bio_youtube
from app.services.instagram_service import fetch_bio_instagram

router = APIRouter(tags=["bios"])
_x = XService()

# FETCHERS: test uyumluluğu için dışa açık dict
# Callable imzası: (username, session=None) -> dict  (sync veya async)
FETCHERS: Dict[str, any] = {
    "x": lambda u, s=None: _x.fetch_bio(u),
    "github": fetch_bio_github,
    "reddit": fetch_bio_reddit,
    "youtube": fetch_bio_youtube,
    "instagram": fetch_bio_instagram,
}

async def _call(fn, username: str) -> Dict:
    """sync veya async callable'ı güvenle çağır."""
    result = fn(username)
    if inspect.isawaitable(result):
        return await result
    return result

async def _gather_bios(username: str, only: Optional[str]) -> List[Dict]:
    order = ["instagram", "github", "reddit", "x", "youtube"]
    if only:
        wanted = {w.strip().lower() for w in only.split(",")}
        order = [k for k in order if k in wanted]

    async def _fetch(k: str) -> Dict:
        try:
            fn = FETCHERS[k]
            result = fn(username)
            if inspect.isawaitable(result):
                return await result
            return result
        except Exception:
            return {"platform": k.title(), "url": "", "status": "unknown", "display_name": "", "bio": ""}

    tasks = [_fetch(k) for k in order]
    results = await asyncio.gather(*tasks, return_exceptions=True)
    out = []
    for r in results:
        if isinstance(r, Exception):
            out.append({"platform": "unknown", "url": "", "status": "unknown", "display_name": "", "bio": ""})
        else:
            out.append(r)
    return out

@router.get("/username-bios")
async def username_bios(username: str = Query(...), only: Optional[str] = Query(None)):
    uname = username.strip().lstrip("@")
    results = await _gather_bios(uname, only)
    return JSONResponse({"username": uname, "count": len(results), "results": results})
