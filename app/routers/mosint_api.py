import asyncio
from fastapi import APIRouter, Query, Request
from app.core.limiter import limiter
import re, os, hashlib, smtplib
import httpx
from urllib.parse import quote

router = APIRouter(prefix="/mosint", tags=["mosint"])

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")
UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120 Safari/537.36"
HDRS = {"User-Agent": UA, "Accept": "application/json"}

def _try_json(resp: httpx.Response):
    try:
        if not resp.text:
            return None
        return resp.json()
    except Exception:
        return None

async def abstract_email_lookup(email: str, timeout: float = 10.0) -> dict:
    key = os.getenv("ABSTRACT_EMAIL_KEY", "").strip()
    if not key:
        return {"ok": False, "error": "ABSTRACT_EMAIL_KEY eksik"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.get(
                "https://emailreputation.abstractapi.com/v1/",
                params={"api_key": key, "email": email}
            )
            data = r.json()
            deliverability = data.get("email_deliverability", {})
            sender = data.get("email_sender", {})
            domain = data.get("email_domain", {})
            quality = data.get("email_quality", {})
            return {
                "ok": True,
                "deliverable": deliverability.get("status"),
                "is_smtp_valid": deliverability.get("is_smtp_valid"),
                "is_mx_valid": deliverability.get("is_mx_valid"),
                "is_format_valid": deliverability.get("is_format_valid"),
                "is_free_email": quality.get("is_free_email"),
                "is_disposable": quality.get("is_disposable_email"),
                "quality_score": quality.get("score"),
                "first_name": sender.get("first_name"),
                "last_name": sender.get("last_name"),
                "provider": sender.get("email_provider_name"),
                "domain_age_days": domain.get("age_days"),
                "domain_registered": domain.get("date_registered"),
            }
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def get_emailrep(email: str, timeout: float) -> dict:
    out = {"ok": False}
    key = os.getenv("EMAILREP_KEY", "").strip()
    try:
        h = dict(HDRS)
        if key:
            h["Key"] = key
        async with httpx.AsyncClient(headers=h, timeout=timeout) as cli:
            r = await cli.get(f"https://emailrep.io/{email}")
            out["status"] = r.status_code
            j = _try_json(r)
            if r.is_success and isinstance(j, dict):
                out["ok"] = True
                out["data"] = j
                return out
            # fallback: r.jina.ai
            r2 = await cli.get(f"https://r.jina.ai/http://emailrep.io/{email}", headers=HDRS)
            out["fallback_status"] = r2.status_code
            j2 = _try_json(r2)
            if r2.is_success and isinstance(j2, dict):
                out["ok"] = True
                out["data"] = j2
    except Exception as e:
        out["error"] = str(e)
    return out

async def doh_mx(domain: str, timeout: float) -> dict:
    try:
        async with httpx.AsyncClient(headers=HDRS, timeout=timeout) as cli:
            r = await cli.get("https://dns.google/resolve", params={"name": domain, "type": "MX"})
        j = _try_json(r) or {}
        mx = []
        for ans in j.get("Answer", []) or []:
            data = ans.get("data", "")
            parts = data.split()
            pref = None
            host = data
            if parts:
                if parts[0].isdigit():
                    pref = int(parts[0]); host = parts[-1]
                host = host.rstrip(".")
            mx.append({"preference": pref, "host": host})
        return {"ok": True, "servers": mx, "raw": j}
    except Exception as e:
        return {"ok": False, "error": str(e)}

def smtp_probe(mx_list, email: str, timeout: float) -> dict:
    res = {"ok": False, "supported": False, "mx_used": None, "code": None}
    try:
        if not mx_list:
            res["error"] = "no mx"; return res
        host = sorted([(m.get("preference") or 50, m["host"]) for m in mx_list])[0][1]
        res["mx_used"] = host
        with smtplib.SMTP(host, 25, timeout=timeout) as s:
            s.ehlo_or_helo_if_needed()
            try:
                code, msg = s.verify(email)
                res.update({"supported": True, "code": int(code), "message": (msg or b"").decode(errors="ignore")})
                res["ok"] = int(code) < 400
                return res
            except smtplib.SMTPNotSupportedError:
                res["supported"] = False
            except Exception as e:
                res["note"] = f"vrfy_fail: {e}"
            try:
                s.mail("probe@mosint.local")
                code, msg = s.rcpt(email)
                res.update({"code": int(code), "message": (msg or b"").decode(errors="ignore")})
                res["ok"] = 200 <= int(code) < 400
            except Exception as e:
                res["error"] = str(e)
    except Exception as e:
        res["error"] = str(e)
    return res

async def gravatar_info(email: str, timeout: float) -> dict:
    try:
        md5 = hashlib.md5(email.strip().lower().encode()).hexdigest()
        async with httpx.AsyncClient(headers=HDRS, timeout=timeout) as cli:
            head = await cli.get(f"https://www.gravatar.com/avatar/{md5}?d=404")
            exists = (head.status_code == 200)
            prof = {}
            try:
                rj = await cli.get(f"https://en.gravatar.com/{md5}.json")
                pj = _try_json(rj) or {}
                prof = pj
            except Exception:
                pass
        return {"hash": md5, "exists": exists, "profile": prof}
    except Exception as e:
        return {"error": str(e)}

async def openpgp_lookup(email: str, timeout: float) -> dict:
    try:
        async with httpx.AsyncClient(headers=HDRS, timeout=timeout) as cli:
            r = await cli.get(f"https://keys.openpgp.org/vks/v1/by-email/{quote(email)}")
        if r.status_code in (404, 204):
            return {"ok": True, "count": 0, "raw": {}}
        j = _try_json(r) or {}
        keys = j.get("keys") or j.get("results") or []
        return {"ok": r.is_success, "count": len(keys), "raw": j}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def hunter_verify(email: str, timeout: float) -> dict:
    key = os.getenv("HUNTER_KEY", "").strip()
    if not key:
        return {"ok": False, "note": "HUNTER_KEY not set"}
    try:
        async with httpx.AsyncClient(headers=HDRS, timeout=timeout) as cli:
            r = await cli.get("https://api.hunter.io/v2/email-verifier",
                              params={"email": email, "api_key": key})
        j = _try_json(r) or {}
        return {"ok": r.is_success, "status": r.status_code, "data": j}
    except Exception as e:
        return {"ok": False, "error": str(e)}

async def hibp_breaches(email: str, timeout: float) -> dict:
    key = os.getenv("HIBP_KEY", "").strip()
    if not key:
        return {"ok": False, "note": "HIBP_KEY not set"}
    try:
        async with httpx.AsyncClient(timeout=timeout) as cli:
            r = await cli.get(
                f"https://haveibeenpwned.com/api/v3/breachedaccount/{quote(email)}",
                headers={"hibp-api-key": key, "user-agent": UA, "Accept": "application/json"},
                params={"truncateResponse": "true"}
            )
        if r.status_code == 404:
            return {"ok": True, "breached": False, "count": 0, "items": []}
        j = _try_json(r) or []
        return {"ok": r.is_success, "status": r.status_code, "breached": r.is_success and bool(j), "count": len(j) if isinstance(j, list) else 0, "items": j}
    except Exception as e:
        return {"ok": False, "error": str(e)}

@router.get("/full")
@limiter.limit("20/minute")
async def mosint_full_route(
    request: Request,
    email: str = Query(..., min_length=5),
    smtp: int = 0,
    deep: int = 0,
    timeout: float = 8.0,
):
    return await mosint_full(email=email, smtp=smtp, deep=deep, timeout=timeout)


async def mosint_full(email: str, smtp: int = 0, deep: int = 0, timeout: float = 8.0):
    out = {
        "email": email,
        "syntax_ok": bool(EMAIL_RE.match(email)),
        "domain": email.split("@")[-1].lower() if "@" in email else None,
        "sources": {},
        "verdict": "unknown"
    }
    if not out["syntax_ok"]:
        out["verdict"] = "invalid_syntax"
        return out

    # Bağımsız çağrıları paralele al
    base_tasks = [
        get_emailrep(email, timeout),
        doh_mx(out["domain"], timeout),
        gravatar_info(email, timeout),
        openpgp_lookup(email, timeout),
        abstract_email_lookup(email, timeout),
    ]
    base_results = await asyncio.gather(*base_tasks, return_exceptions=True)

    def _safe(r, fallback):
        return fallback if isinstance(r, Exception) else r

    er  = _safe(base_results[0], {"ok": False, "error": "gather_fail"})
    mx  = _safe(base_results[1], {"ok": False, "servers": [], "error": "gather_fail"})
    grav = _safe(base_results[2], {"exists": False})
    pgp  = _safe(base_results[3], {"ok": False})
    abst = _safe(base_results[4], {"ok": False})

    out["sources"]["emailrep"] = er
    out["sources"]["mx"] = mx
    out["sources"]["gravatar"] = grav
    out["sources"]["openpgp"] = pgp
    out["sources"]["abstract_email"] = abst

    if smtp:
        out["sources"]["smtp"] = smtp_probe(mx.get("servers") or [], email, timeout)

    if deep:
        deep_results = await asyncio.gather(
            hunter_verify(email, timeout),
            hibp_breaches(email, timeout),
            return_exceptions=True
        )
        out["sources"]["hunter"] = _safe(deep_results[0], {"ok": False})
        out["sources"]["hibp"]   = _safe(deep_results[1], {"ok": False})

    suspicious = False
    try:
        d = er.get("data", {}) if isinstance(er, dict) else {}
        suspicious = bool(d.get("suspicious")) or bool(d.get("details", {}).get("malicious_activity"))
    except Exception:
        pass
    out["verdict"] = "suspicious" if suspicious else "ok"

    # Cleanup
    try:
        er_src = out["sources"].get("emailrep", {})
        def _clean_er(d):
            if not isinstance(d, dict):
                return
            d.pop("content", None); d.pop("metadata", None); d.pop("external", None)
            d.pop("usage", None); d.pop("publishedTime", None); d.pop("meta", None)
            for v in d.values():
                if isinstance(v, dict):
                    _clean_er(v)
        _clean_er(er_src)
    except Exception:
        pass
    try:
        del out["sources"]["mx"]["raw"]
    except (KeyError, TypeError):
        pass
    try:
        del out["sources"]["openpgp"]["raw"]
    except (KeyError, TypeError):
        pass
    try:
        if not out["sources"]["gravatar"]["exists"]:
            del out["sources"]["gravatar"]["profile"]
    except (KeyError, TypeError):
        pass

    return out

__all__ = ["mosint_full"]
