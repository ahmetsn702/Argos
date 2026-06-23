"""Instagram consolidated router — tüm aktif IG endpoint'leri burada."""
from typing import List, Optional
from fastapi import APIRouter, Query, Form
from fastapi.responses import JSONResponse, Response

from app.services.instagram_service import InstagramService
from app.services.ig_media import fetch_recent_media, fetch_media_html

router = APIRouter(tags=["instagram"])
_svc = InstagramService()


# ── /ig/bio ───────────────────────────────────────────────────────────────────
@router.get("/ig/bio")
async def ig_bio(username: str = Query(..., min_length=1), debug: int = Query(0)):
    u = username.strip().lstrip("@")
    data = await _svc.get_bio(u)
    if "error" in data:
        out = {"username": u, "bio": None, "source": "none", "error": data["error"]}
        if debug >= 1:
            out["debug"] = {}
        return JSONResponse(out)
    out = {
        "username": u,
        "bio": data.get("biography") or data.get("bio"),
        "full_name": data.get("full_name", ""),
        "source": data.get("source", "service"),
    }
    if debug >= 1:
        out["debug"] = {"cache": "service"}
    return JSONResponse(out)


# ── /ig-profile ───────────────────────────────────────────────────────────────
@router.get("/ig-profile")
async def ig_profile(username: str = Query(..., min_length=1)):
    u = username.strip().lstrip("@")
    return await _svc.get_profile(u)


# ── /v2/ig-profile ────────────────────────────────────────────────────────────
@router.get("/v2/ig-profile")
async def ig_profile_v2(username: str = Query(..., min_length=1)):
    u = username.strip().lstrip("@")
    return await _svc.get_profile(u)


# ── /hunt-ig-by-name ──────────────────────────────────────────────────────────
@router.get("/hunt-ig-by-name")
async def hunt_ig_by_name(
    full_name: str = Query(..., min_length=2),
    limit: int = Query(default=40, ge=1, le=60),
):
    results = await _svc.search(full_name, limit=limit)
    return JSONResponse({"full_name": full_name, "results": results,
                         "candidates_tried": len(results)})


# ── /v2/hunt-ig-by-name ───────────────────────────────────────────────────────
@router.get("/v2/hunt-ig-by-name")
async def hunt_ig_by_name_v2(
    full_name: str = Query(..., min_length=2),
    limit: int = Query(default=60, ge=1, le=100),
):
    results = await _svc.search(full_name, limit=limit)
    return JSONResponse({"full_name": full_name, "results": results,
                         "candidates_tried": len(results)})


# ── /tester/ig-media ──────────────────────────────────────────────────────────
@router.post("/tester/ig-media")
async def ig_media(user: str = Form(...), limit: int = Form(9)):
    return JSONResponse(await fetch_recent_media((user or "").strip(), limit))


# ── /tester/ig-media-lite ─────────────────────────────────────────────────────
@router.post("/tester/ig-media-lite")
async def ig_media_lite(user: str = Form(...), limit: int = Form(9)):
    user = (user or "").strip().lstrip("@")
    if not user:
        return JSONResponse({"ok": False, "error": "user required"}, status_code=400)
    return JSONResponse(await fetch_media_html(user, limit))
