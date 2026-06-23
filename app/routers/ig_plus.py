# app/routers/ig_plus.py
# -*- coding: utf-8 -*-
"""IG tester router. Logic lives in services/templates modules."""
from __future__ import annotations

from fastapi import APIRouter, Form, Query
from fastapi.responses import HTMLResponse, JSONResponse, PlainTextResponse, Response

from app.services.ig_media import build_media_zip, fetch_media_html, fetch_recent_media
from app.services.ig_profile import compare_ig_x_plus as svc_compare_ig_x_plus
from app.templates import ig_plus_bridge as bridge
from app.templates import ig_plus_ui as ui
from app.utils.ig_helpers import fetch_proxy_image, ok_pp_proxy_host, ok_proxy_host

router = APIRouter(prefix="/tester", tags=["tester"])


def _register_static(path: str, fn, response_class):
    async def _h():
        return fn()
    _h.__name__ = "static_" + path.strip("/").replace("-", "_").replace(".", "_")
    router.add_api_route(path, _h, methods=["GET"], response_class=response_class)


for _path, _fn in (
    ("/ig-bio-ui-pro", ui.ig_bio_ui_pro),
    ("/pro", ui.tester_pro),
    ("/pro2", ui.tester_pro2),
):
    _register_static(_path, _fn, HTMLResponse)

for _path, _fn in (
    ("/pro-bridge.js", bridge.pro_bridge),
    ("/pro-bridge-v2.js", bridge.pro_bridge_v2),
    ("/pro-bridge-v3.js", bridge.pro_bridge_v3),
    ("/pro-bridge-v4.js", bridge.pro_bridge_v4),
    ("/pro-bridge-v5.js", bridge.pro_bridge_v5),
    ("/pro-bridge-v6.js", bridge.pro_bridge_v6),
    ("/pro-bridge-compact.js", bridge.pro_bridge_compact),
    ("/head-mini.js", bridge.head_mini),
):
    _register_static(_path, _fn, PlainTextResponse)


@router.get("/ig-bio-ui", include_in_schema=False)
def ig_bio_ui():
    return HTMLResponse(ui.ig_bio_ui())


@router.post("/compare-ig-x-plus")
async def compare_ig_x_plus(user: str = Form(...), prefer_native: int = Form(0), with_bio: int = Form(1)):
    return JSONResponse(await svc_compare_ig_x_plus(user, prefer_native, with_bio))


@router.post("/ig-media-zip5")
async def ig_media_zip5(user: str = Form(...), limit: int = Form(12)):
    blob = await build_media_zip(user, limit)
    if blob is None:
        return Response(status_code=404, content=b"profile not reachable or no media")
    fn = (user or "ig").strip().lstrip("@") + "_media.zip"
    return Response(blob, media_type="application/zip",
                    headers={"Content-Disposition": f'attachment; filename="{fn}"'})


def _proxy_response(result):
    return Response(content=result["content"], status_code=result["status_code"],
                    media_type=result["media_type"], headers=result["headers"])


@router.get("/ig-proxy")
async def ig_proxy(url: str = Query(...)):
    res = await fetch_proxy_image(url, host_check=ok_proxy_host, cache_control="no-store")
    if res["status_code"] in (400, 403):
        return Response(status_code=400, content=b"bad url")
    return _proxy_response(res)


@router.get("/pp-proxy")
async def pp_proxy(u: str = Query(...)):
    return _proxy_response(await fetch_proxy_image(u, host_check=ok_pp_proxy_host, cache_control="public, max-age=600"))
