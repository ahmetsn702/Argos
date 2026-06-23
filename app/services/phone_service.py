import re
import httpx
from typing import Optional
from app.core.config import settings

def normalize_phone(number: str) -> str:
    number = re.sub(r"[^\d+]", "", number.strip())
    if number.startswith("0") and not number.startswith("00"):
        number = "+90" + number[1:]
    if not number.startswith("+"):
        number = "+" + number
    return number

async def numverify_lookup(number: str, timeout: float = 10.0) -> dict:
    key = getattr(settings, "NUMVERIFY_KEY", None)
    if not key:
        return {"ok": False, "error": "NUMVERIFY_KEY eksik"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.get(
                "http://apilayer.net/api/validate",
                params={"access_key": key, "number": number, "country_code": "", "format": 1}
            )
            data = r.json()
            return {
                "ok": True,
                "valid": data.get("valid"),
                "number": data.get("international_format"),
                "local": data.get("local_format"),
                "country": data.get("country_name"),
                "carrier": data.get("carrier"),
                "line_type": data.get("line_type"),
                "location": data.get("location"),
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def abstract_phone_lookup(number: str, timeout: float = 10.0) -> dict:
    key = getattr(settings, "ABSTRACT_PHONE_KEY", None)
    if not key:
        return {"ok": False, "error": "ABSTRACT_PHONE_KEY eksik"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.get(
                "https://phoneintelligence.abstractapi.com/v1/",
                params={"api_key": key, "phone": number}
            )
            data = r.json()
            carrier = data.get("phone_carrier", {})
            location = data.get("phone_location", {})
            fmt = data.get("phone_format", {})
            messaging = data.get("phone_messaging", {})
            return {
                "ok": True,
                "number": data.get("phone_number"),
                "international_format": fmt.get("international"),
                "valid": True,
                "country": location.get("country_name"),
                "country_code": location.get("country_code"),
                "region": location.get("region"),
                "city": location.get("city"),
                "timezone": location.get("timezone"),
                "carrier": carrier.get("name"),
                "line_type": carrier.get("line_type"),
                "sms_supported": messaging.get("sms_domain") != "unknown",
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def veriphone_lookup(number: str, timeout: float = 10.0) -> dict:
    key = getattr(settings, "VERIPHONE_KEY", None)
    if not key:
        return {"ok": False, "error": "VERIPHONE_KEY eksik"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.get(
                "https://api.veriphone.io/v2/verify",
                params={"phone": number, "key": key}
            )
            data = r.json()
            if data.get("status") == "error":
                return {"ok": False, "error": data.get("message", "Veriphone API hatasi")}
            return {
                "ok": True,
                "valid": data.get("phone_valid"),
                "number": data.get("international_number"),
                "local": data.get("local_number"),
                "country": data.get("country"),
                "carrier": data.get("carrier"),
                "line_type": data.get("phone_type"),
                "location": data.get("phone_region"),
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def phone_osint(number: str, timeout: float = 10.0) -> dict:
    import asyncio
    normalized = normalize_phone(number)
    
    # 1) Try Numverify first, and run Abstract Phone in parallel
    numverify, abstract = await asyncio.gather(
        numverify_lookup(normalized, timeout),
        abstract_phone_lookup(normalized, timeout),
        return_exceptions=True
    )
    
    nv_res = numverify if not isinstance(numverify, Exception) else {"ok": False, "error": str(numverify)}
    ab_res = abstract if not isinstance(abstract, Exception) else {"ok": False, "error": str(abstract)}

    # 2) Fallback to Veriphone if Numverify is not configured or failed
    vp_res = None
    if not nv_res.get("ok") or not nv_res.get("valid"):
        vp_res = await veriphone_lookup(normalized, timeout)

    return {
        "input": number,
        "normalized": normalized,
        "numverify": nv_res,
        "veriphone": vp_res,
        "abstract": ab_res,
    }

