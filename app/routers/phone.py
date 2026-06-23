from fastapi import APIRouter, Query, HTTPException, Request
from app.services.phone_service import phone_osint
from app.core.limiter import limiter

router = APIRouter(prefix="/phone", tags=["phone"])

@router.get("/lookup")
@limiter.limit("30/minute")
async def phone_lookup(
    request: Request,
    number: str = Query(..., description="Telefon numarası (örn. +905xxxxxxxxx veya 05xxxxxxxxx)"),
    timeout: float = Query(10.0, ge=3.0, le=30.0)
):
    if len(number.strip()) < 7:
        raise HTTPException(status_code=400, detail="Geçersiz numara")
    return await phone_osint(number, timeout)
