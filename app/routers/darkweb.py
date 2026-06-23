from fastapi import APIRouter, Query, HTTPException, Request
from app.services.darkweb_service import darkweb_osint
from app.core.limiter import limiter

router = APIRouter(prefix="/darkweb", tags=["darkweb"])

@router.get("/lookup")
@limiter.limit("20/minute")
async def darkweb_lookup(
    request: Request,
    query: str = Query(..., description="Email, kullanıcı adı veya telefon numarası"),
    type: str = Query("auto", description="Sorgu tipi: auto, email, username, phone"),
    timeout: float = Query(10.0, ge=3.0, le=30.0)
):
    if len(query.strip()) < 3:
        raise HTTPException(status_code=400, detail="Sorgu çok kısa")
    return await darkweb_osint(query, type, timeout)
