# -*- coding: utf-8 -*-
from fastapi import APIRouter, Query
from app.services.fb_service import get_fb_profile
from app.services.fb_photos import get_fb_photos

router = APIRouter()

@router.get("/fb-profile")
async def fb_profile(username: str = Query(..., description="facebook kullanıcı adı (page veya profil)")):
    return await get_fb_profile(username)

@router.get("/fb-photos")
async def fb_photos(username: str, limit: int = 12):
    limit = max(1, min(50, limit))
    return await get_fb_photos(username, limit=limit)
