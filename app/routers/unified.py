# -*- coding: utf-8 -*-
import asyncio
import time
import hashlib
import logging
from typing import Optional, Dict, Any
from fastapi import APIRouter, Query, HTTPException, Request
from fastapi.responses import JSONResponse
from app.utils import pw_monkeypatch
pw_monkeypatch.apply()

from app.core.limiter import limiter

# Mevcut servisleri import et
from app.routers.mosint_api import mosint_full
from app.routers.hunt_social import _hunt_impl
from app.routers.linkedin_public import linkedin_public
from app.services.hibp_service import hibp_breached_account
from app.utils.cache import cache_get, cache_set, ig_cache
from app.core.config import settings

# PersonCard kanalı (POST /scan/full) için.
from app.models.person import PersonQuery
from app.services.person_aggregator import build_person_card

router = APIRouter(prefix="/scan", tags=["unified"])

# Logger
logger = logging.getLogger("footprint")

def _normalize_input(email: Optional[str] = None, username: Optional[str] = None, phone: Optional[str] = None) -> str:
    """Input'u normalize et ve cache key oluştur"""
    parts = []
    if email:
        parts.append(f"email:{email.strip().lower()}")
    if username:
        parts.append(f"username:{username.strip().lower()}")
    if phone:
        parts.append(f"phone:{phone.strip()}")
    return "|".join(parts)

def _get_cache_key(endpoint: str, normalized_input: str) -> str:
    """Cache key oluştur"""
    content = f"{endpoint}:{normalized_input}"
    return hashlib.sha1(content.encode()).hexdigest()

async def _call_mosint_api(email: str, timeout: float) -> Dict[str, Any]:
    """Mosint API'yi çağır"""
    start_time = time.time()
    try:
        # Mosint API'yi async olarak çağır
        result = await mosint_full(email=email, timeout=timeout)
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"mosint_api completed in {duration_ms}ms")
        return {
            "ok": True,
            "duration_ms": duration_ms,
            "data": result,
            "error": None
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"mosint_api failed in {duration_ms}ms: {str(e)}")
        return {
            "ok": False,
            "duration_ms": duration_ms,
            "data": None,
            "error": str(e)
        }

async def _call_social_hunt(full_name: str, keywords: list, timeout: float) -> Dict[str, Any]:
    """Social hunt API'yi çağır"""
    start_time = time.time()
    try:
        result = await _hunt_impl(full_name, keywords, limit=40, stop_at=0.90)
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"social_hunt completed in {duration_ms}ms")
        return {
            "ok": True,
            "duration_ms": duration_ms,
            "data": result,
            "error": None
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"social_hunt failed in {duration_ms}ms: {str(e)}")
        return {
            "ok": False,
            "duration_ms": duration_ms,
            "data": None,
            "error": str(e)
        }

async def _call_linkedin_public(slug: str, timeout: float) -> Dict[str, Any]:
    """LinkedIn public API'yi çağır"""
    start_time = time.time()
    try:
        # LinkedIn public'ı sync olarak çağır
        result = await asyncio.get_event_loop().run_in_executor(
            None,
            lambda: linkedin_public(slug=slug)
        )
        duration_ms = int((time.time() - start_time) * 1000)
        
        logger.info(f"linkedin_public completed in {duration_ms}ms")
        return {
            "ok": True,
            "duration_ms": duration_ms,
            "data": result,
            "error": None
        }
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"linkedin_public failed in {duration_ms}ms: {str(e)}")
        return {
            "ok": False,
            "duration_ms": duration_ms,
            "data": None,
            "error": str(e)
        }

async def _scan_full_legacy(
    email: Optional[str] = None,
    username: Optional[str] = None,
    phone: Optional[str] = None,
    timeout: float = 15.0,
) -> Dict[str, Any]:
    """
    Birleşik tarama iç helper'ı — HTTP'siz, in-process çağrılabilir.

    GET /scan/full handler'ı bu fonksiyonu çağırır. person_aggregator da
    bu fonksiyonu doğrudan çağırarak rekürsif HTTP loop'undan kaçınır.

    Davranış GET endpoint'i ile birebir aynıdır: aynı cache key, aynı
    response shape, aynı verdict mantığı. Yalnız HTTPException raise
    etmez — boş input gelirse `verdict=fail` döner (HTTP handler 400'ü
    kendisi raise eder).
    """
    start_time = time.time()

    # Cache key oluştur
    normalized_input = _normalize_input(email, username, phone)
    cache_key = _get_cache_key("scan_full", normalized_input)

    # Cache kontrolü
    cached_result = cache_get(ig_cache, cache_key)
    if cached_result:
        logger.info(f"Returning cached result for {normalized_input}")
        return cached_result

    task_timeout = min(timeout, 10.0)

    async def _wrap_task(coro, name):
        try:
            return await asyncio.wait_for(coro, timeout=task_timeout)
        except asyncio.TimeoutError:
            logger.warning(f"Task {name} timed out after {task_timeout} seconds")
            return {"ok": False, "error": "timeout"}
        except Exception as e:
            logger.error(f"Task {name} failed: {e}")
            return {"ok": False, "error": str(e)}

    # Asenkron görevleri hazırla
    tasks = []
    task_names = []

    # Mosint API (email varsa)
    if email:
        tasks.append(_wrap_task(_call_mosint_api(email, task_timeout), "mosint"))
        task_names.append("mosint")

    # HIBP API (email varsa ve etkinse)
    if email and settings.HIBP_ENABLED and settings.HIBP_KEY:
        tasks.append(_wrap_task(hibp_breached_account(email, task_timeout), "hibp"))
        task_names.append("hibp")

    # Social hunt (username varsa, full_name olarak kullan)
    if username:
        tasks.append(_wrap_task(_call_social_hunt(username, [], task_timeout), "social"))
        task_names.append("social")

    # LinkedIn public (username varsa slug olarak kullan)
    if username:
        tasks.append(_wrap_task(_call_linkedin_public(username, task_timeout), "linkedin"))
        task_names.append("linkedin")

    # Tüm görevleri paralel çalıştır
    results = await asyncio.gather(*tasks, return_exceptions=True) if tasks else []

    # Sonuçları organize et
    response_data: Dict[str, Any] = {
        "input": {
            "email": email,
            "username": username,
            "phone": phone,
        },
        "results": {},
        "verdict": "fail",
        "took_ms": int((time.time() - start_time) * 1000),
    }

    # Sonuçları kategorilere ayır
    for task_name, result in zip(task_names, results):
        if isinstance(result, Exception):
            response_data["results"][task_name] = {
                "ok": False,
                "duration_ms": 0,
                "data": None,
                "error": str(result),
            }
        else:
            response_data["results"][task_name] = result

    # Verdict belirle
    successful_sources = sum(1 for r in response_data["results"].values() if r.get("ok", False))
    total_sources = len(response_data["results"])

    if total_sources == 0:
        response_data["verdict"] = "fail"
    elif successful_sources == total_sources:
        response_data["verdict"] = "ok"
    elif successful_sources > 0:
        response_data["verdict"] = "partial"
    else:
        response_data["verdict"] = "fail"

    # took_ms'i son güncellemeyle yenile
    response_data["took_ms"] = int((time.time() - start_time) * 1000)

    # Cache'e kaydet (sadece başarılı sonuçlar)
    if response_data["verdict"] in ("ok", "partial"):
        cache_set(ig_cache, cache_key, response_data)

    logger.info(
        f"scan_full completed: {response_data['verdict']} "
        f"({successful_sources}/{total_sources} sources successful)"
    )

    return response_data


@router.get("/full")
@limiter.limit("15/minute")
async def scan_full(
    request: Request,
    email: Optional[str] = Query(None, min_length=5),
    username: Optional[str] = Query(None, min_length=1),
    phone: Optional[str] = Query(None, min_length=10),
    timeout: float = Query(15.0, ge=5.0, le=60.0),
):
    """
    Birleşik tarama endpoint'i (legacy GET kanalı). Tek tanımlayıcı tabanlı
    paralel sorgular. POST /scan/full ise zengin PersonQuery body alır ve
    PersonCard döndürür.
    """
    if not any([email, username, phone]):
        raise HTTPException(
            status_code=400,
            detail="At least one of email, username, or phone must be provided",
        )
    response_data = await _scan_full_legacy(
        email=email, username=username, phone=phone, timeout=timeout
    )
    return JSONResponse(response_data)


@router.post("/full")
@limiter.limit("15/minute")
async def scan_full_post(request: Request, query: PersonQuery):
    """
    PersonCard kanalı: zengin `PersonQuery` body alır, `build_person_card`
    servisini çağırır ve `PersonCard` JSON döndürür.

    Body örneği:
    ```json
    {
      "first_name": "Ali",
      "last_name": "Veli",
      "hometown": "Istanbul",
      "hints": {
        "emails": ["ali@example.com"],
        "usernames": ["aliveli"],
        "phones": ["+905551112233"]
      },
      "fast": true,
      "timeout": 30
    }
    ```
    """
    base_url = str(request.base_url).rstrip("/")
    card = await build_person_card(query, base_url=base_url)
    return JSONResponse(card.model_dump())