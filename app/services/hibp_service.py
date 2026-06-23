# -*- coding: utf-8 -*-
import time
import logging
import hashlib
from typing import Dict, Any, Optional
import httpx
from app.core.config import settings
from app.utils.cache import cache_get, cache_set, ig_cache

logger = logging.getLogger("footprint")

async def hibp_breached_account(email: str, timeout: float = 10.0) -> Dict[str, Any]:
    """
    Have I Been Pwned API ile email kontrolü
    """
    start_time = time.time()
    
    # Email normalize: trim + lower
    email_norm = email.strip().lower()
    
    # Cache key = sha1("hibp:" + email_norm)
    cache_key = hashlib.sha1(f"hibp:{email_norm}".encode()).hexdigest()
    cached_result = cache_get(ig_cache, cache_key)
    if cached_result:
        logger.info(f"HIBP cache hit for {email}")
        return cached_result
    
    # API key kontrolü
    if not settings.HIBP_KEY:
        duration_ms = int((time.time() - start_time) * 1000)
        logger.warning(f"HIBP_KEY not configured")
        return {
            "ok": False,
            "duration_ms": duration_ms,
            "data": None,
            "error": "missing HIBP_KEY"
        }
    
    headers = {
        "hibp-api-key": settings.HIBP_KEY,
        "User-Agent": "footprint-backend/hibp",
        "Accept": "application/json"
    }
    
    url = f"https://haveibeenpwned.com/api/v3/breachedaccount/{email_norm}"
    params = {"truncateResponse": "true"}
    
    try:
        async with httpx.AsyncClient(timeout=timeout) as client:
            response = await client.get(url, headers=headers, params=params)
            duration_ms = int((time.time() - start_time) * 1000)
            
            if response.status_code == 200:
                # Email pwned
                breaches = response.json()
                result = {
                    "ok": True,
                    "duration_ms": duration_ms,
                    "data": {
                        "is_pwned": True,
                        "breaches_count": len(breaches),
                        "breaches_list": [breach.get("Name", "") for breach in breaches]
                    },
                    "error": None
                }
                logger.info(f"HIBP check for {email_norm} status pwned took {duration_ms}ms")
                # Cache successful result
                cache_set(ig_cache, cache_key, result)
                return result
                
            elif response.status_code == 404:
                # Email not pwned (normal case)
                result = {
                    "ok": True,
                    "duration_ms": duration_ms,
                    "data": {
                        "is_pwned": False,
                        "breaches_count": 0,
                        "breaches_list": []
                    },
                    "error": None
                }
                logger.info(f"HIBP check for {email_norm} status clean took {duration_ms}ms")
                # Cache successful result
                cache_set(ig_cache, cache_key, result)
                return result
                
            elif response.status_code == 401:
                error_msg = "HIBP API key invalid"
                logger.warning(f"HIBP 401 for {email_norm}: {error_msg}")
                return {
                    "ok": False,
                    "duration_ms": duration_ms,
                    "data": None,
                    "error": error_msg
                }
                
            elif response.status_code == 429:
                error_msg = "HIBP rate limit exceeded"
                logger.warning(f"HIBP 429 for {email_norm}: {error_msg}")
                return {
                    "ok": False,
                    "duration_ms": duration_ms,
                    "data": None,
                    "error": error_msg
                }
                
            else:
                error_msg = f"status={response.status_code} body={response.text[:500]}"
                logger.warning(f"HIBP {response.status_code} for {email_norm}: {error_msg}")
                return {
                    "ok": False,
                    "duration_ms": duration_ms,
                    "data": None,
                    "error": error_msg
                }
                
    except httpx.TimeoutException:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = f"HIBP timeout after {timeout}s"
        logger.warning(f"HIBP timeout for {email_norm}: {error_msg}")
        return {
            "ok": False,
            "duration_ms": duration_ms,
            "data": None,
            "error": error_msg
        }
        
    except Exception as e:
        duration_ms = int((time.time() - start_time) * 1000)
        error_msg = f"HIBP error: {str(e)}"
        logger.warning(f"HIBP exception for {email_norm}: {error_msg}")
        return {
            "ok": False,
            "duration_ms": duration_ms,
            "data": None,
            "error": error_msg
        }
