# app/routers/debug_x.py
# -*- coding: utf-8 -*-
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
from app.services.x_fetch import XService

router = APIRouter(tags=["debug-x"])
_x = XService()

@router.get("/x/__ping")
def x_ping():
    return {"ok": True, "service": "x-debug"}

@router.get("/x/profile")
def x_profile(username: str = Query(..., min_length=1)):
    return JSONResponse(_x.profile(username))

@router.get("/x/fast-profile")
def x_fast_profile(username: str = Query(..., min_length=1)):
    return JSONResponse(_x.fast_profile(username))
