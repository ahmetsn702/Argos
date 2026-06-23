from fastapi import APIRouter, Query, HTTPException, Request
from app.services.news_service import search_tr_news
from app.core.limiter import limiter

router = APIRouter(prefix="/tr", tags=["news"])


@router.get("/haberler")
@limiter.limit("30/minute")
async def haberler(
    request: Request,
    q: str = Query(..., description="Arama sorgusu"),
    limit: int = Query(10, ge=1, le=50)
):
    if not q or not q.strip():
        raise HTTPException(status_code=400, detail="Sorgu (q) boş olamaz.")
    return await search_tr_news(q.strip(), limit=limit)
