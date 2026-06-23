from fastapi import APIRouter, Query, HTTPException, Request
from app.services.domain_service import domain_osint
from app.core.limiter import limiter

router = APIRouter(prefix="/domain", tags=["domain"])

@router.get("/lookup")
@limiter.limit("30/minute")
async def domain_lookup(
    request: Request,
    target: str = Query(..., description="Domain adı veya IP adresi"),
    timeout: float = Query(10.0, ge=3.0, le=30.0)
):
    if len(target.strip()) < 3:
        raise HTTPException(status_code=400, detail="Geçersiz hedef")
    return await domain_osint(target, timeout)
