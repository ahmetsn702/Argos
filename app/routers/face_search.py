from fastapi import APIRouter, File, UploadFile, Form, HTTPException, Request
from fastapi.responses import JSONResponse
from typing import Optional
from app.services.face_service import run_face_search
from app.core.limiter import limiter
from app.core.config import settings

router = APIRouter(prefix="/face", tags=["face"])

@router.post("/search")
@limiter.limit("10/minute")
async def face_search(
    request: Request,
    image: UploadFile = File(...),
    engines: Optional[str] = Form("saucenao,google_vision"),
    max_results: int = Form(10),
):
    """
    Yüklenen fotoğraftaki yüzü tanımaya çalışır.
    engines: virgülle ayrılmış liste → yandex, google_vision, local
    """
    if image.content_type not in ("image/jpeg", "image/png", "image/webp"):
        raise HTTPException(status_code=400, detail="Sadece JPEG/PNG/WebP desteklenir")

    image_bytes = await image.read()
    if len(image_bytes) > 10 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Dosya 10MB sinirini asiyor")

    engine_list = [e.strip() for e in (engines or "").split(",") if e.strip()]
    result = await run_face_search(image_bytes, engine_list, max_results)
    return JSONResponse(result)


@router.get("/health")
async def face_health():
    engines = {}
    try:
        import face_recognition  # noqa: F401
        engines["local_face_recognition"] = True
    except ImportError:
        engines["local_face_recognition"] = False

    from app.services.yandex_search import _PW_AVAILABLE
    engines["yandex_playwright"] = _PW_AVAILABLE

    import os
    engines["google_vision"] = bool(
        os.getenv("GOOGLE_API_KEY") or os.getenv("GOOGLE_CSE_API_KEY")
    )
    engines["saucenao"] = bool(settings.SAUCENAO_API_KEY)
    engines["tineye"] = bool(settings.TINEYE_KEY)
    return {"status": "ok", "engines": engines}
