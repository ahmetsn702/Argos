from fastapi import APIRouter, Query
from app.services.tc_service import verify_tc

router = APIRouter(prefix="/tr", tags=["turkey"])


@router.get("/tc")
async def tc_verify(
    tc: str = Query(..., description="11 haneli TC Kimlik No"),
    ad: str = Query(...),
    soyad: str = Query(...),
    dogum_yili: int = Query(..., ge=1900, le=2100),
):
    return await verify_tc(tc_no=tc, ad=ad, soyad=soyad, dogum_yili=dogum_yili)
