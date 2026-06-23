import asyncio
from typing import Optional
from fastapi import APIRouter, Query, HTTPException
from fastapi.responses import JSONResponse
from app.services.scan_service import PLATFORMS, probe_single

router = APIRouter(tags=["scan"])

@router.get("/username-scan")
async def username_scan(username: str = Query(...), only: Optional[str] = Query(None)):
    uname = username.strip().lstrip("@")
    if not uname:
        raise HTTPException(status_code=400, detail="username boş olamaz.")
    selected = PLATFORMS
    if only:
        wanted = {x.strip().lower() for x in only.split(",")}
        selected = [p for p in PLATFORMS if p.name.lower() in wanted]
        if not selected:
            raise HTTPException(status_code=400, detail="Seçilen platformlar eşleşmedi.")
    tasks = [probe_single(uname, p) for p in selected]
    raw = await asyncio.gather(*tasks, return_exceptions=True)
    results = [r for r in raw if not isinstance(r, Exception)]
    return JSONResponse({"username": uname, "count": len(results), "results": results})
