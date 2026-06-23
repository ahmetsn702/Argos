from fastapi import APIRouter, Query
from app.services.mersis_service import query_mersis

router = APIRouter(prefix="/tr", tags=["turkey"])


@router.get("/mersis")
async def mersis_lookup(q: str = Query(..., min_length=2)):
    return await query_mersis(q)
