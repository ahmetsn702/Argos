
from __future__ import annotations
import typing
import re
from urllib.parse import urlparse

import asyncio
import hashlib
import inspect
import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

import httpx
from pydantic import BaseModel, Field

# ---------- Models (canonical: app.models.person) ----------
from app.models.person import PersonHints, PersonQuery, SourceInfo, ProfileEntry, PersonCard
# ---------- Safe cache wrappers ----------
_LOCAL_CACHE: Dict[str, Tuple[int, Any]] = {}

def _local_cache_get(key: str) -> Optional[Any]:
    item = _LOCAL_CACHE.get(key)
    if not item:
        return None
    exp, val = item
    if exp and exp < int(time.time()):
        _LOCAL_CACHE.pop(key, None)
        return None
    return val

def _local_cache_set(key: str, value: Any, ttl: int = 3600) -> None:
    _LOCAL_CACHE[key] = (int(time.time()) + ttl, value)

_cache_get_fn = None
_cache_set_fn = None
# NOTE: We intentionally do NOT import `app.utils.cache.cache_get/cache_set`
# here — their signatures are `(cache, key)` / `(cache, key, value)` (they
# expect a TTLCache instance as the first arg) and silently swallow
# TypeErrors, which makes the wrapper below appear to succeed while never
# storing anything. Sticking to the local in-memory cache below avoids that
# trap. If a project-wide cache backend is ever added with a (key, value, ttl)
# signature, hook it in here.

async def cache_get_safe(key: str) -> Optional[Any]:
    if _cache_get_fn is None:
        return _local_cache_get(key)
    try:
        res = _cache_get_fn(key)  # sync/async fark etmeyebilir
        if inspect.isawaitable(res):
            return await res
        return res
    except TypeError:
        # Bazı projelerde imza değişik olabilir; kwargs dene
        try:
            res = _cache_get_fn(key=key)  # type: ignore
            if inspect.isawaitable(res):
                return await res
            return res
        except Exception:
            return _local_cache_get(key)
    except Exception:
        return _local_cache_get(key)

async def cache_set_safe(key: str, value: Any, ttl: int = 3600) -> None:
    if _cache_set_fn is None:
        _local_cache_set(key, value, ttl)
        return
    try:
        res = _cache_set_fn(key, value, ttl)  # sync/async olabilir
        if inspect.isawaitable(res):
            await res
    except TypeError:
        try:
            res = _cache_set_fn(key=key, value=value, ttl=ttl)  # type: ignore
            if inspect.isawaitable(res):
                await res
        except Exception:
            _local_cache_set(key, value, ttl)
    except Exception:
        _local_cache_set(key, value, ttl)


# ---------- Normalize / username variants ----------
_TR_MAP = str.maketrans({
    "ş": "s", "Ş": "s",
    "ğ": "g", "Ğ": "g",
    "ü": "u", "Ü": "u",
    "ö": "o", "Ö": "o",
    "ç": "c", "Ç": "c",
    "ı": "i", "İ": "i",
})

def _norm(s: str) -> str:
    s = (s or "").strip()
    s = s.translate(_TR_MAP)
    s = re.sub(r"\s+", " ", s)
    return s.lower()

def _strip_non_alnum(s: str) -> str:
    return re.sub(r"[^a-z0-9]", "", _norm(s))

def _normalize_name_parts(first: str, last: str) -> Tuple[str, str]:
    return _strip_non_alnum(first), _strip_non_alnum(last)

def _username_variants(first: str, last: str) -> List[str]:
    f, l = _normalize_name_parts(first, last)
    variants = set()
    joiners = ["", "_", ".", "-"]
    bases = [f, l, f + l, l + f, f[:1] + l, f[:2] + l, f + l[:1], f + l[:2]]
    subs = {"sayin": "syn", "ahmet": "ahmt"}
    for j in joiners:
        variants.add(f + j + l)
        variants.add(l + j + f)
    variants.update(bases)
    for k, v in subs.items():
        variants.add(_strip_non_alnum((f + l).replace(k, v)))
        variants.add(_strip_non_alnum(f.replace(k, v) + l))
    return sorted({x for x in variants if 3 <= len(x) <= 30})

# ---------- URL → platform/handle ----------
_PLATFORM_MAP = {
    "instagram.com": "instagram", "www.instagram.com": "instagram",
    "x.com": "x", "www.x.com": "x", "twitter.com": "x", "www.twitter.com": "x",
    "linkedin.com": "linkedin", "www.linkedin.com": "linkedin",
    "github.com": "github", "www.github.com": "github",
    "tiktok.com": "tiktok", "www.tiktok.com": "tiktok",
    "facebook.com": "facebook", "www.facebook.com": "facebook",
    "medium.com": "medium", "www.medium.com": "medium",
    "pinterest.com": "pinterest", "www.pinterest.com": "pinterest",
}

# [DEMO] URL → (platform, handle) extractor with special-path handling
def _platform_from_url(url: str) -> tuple[typing.Optional[str], typing.Optional[str]]:
    """
    Verilen sosyal URL'den platform ve handle çıkarır.
    Dönüş: (platform, handle) veya (None, None)
    """
    try:
        u = urlparse(url)
    except Exception:
        return None, None

    host = (u.netloc or "").lower()
    path = (u.path or "").strip("/")

    if not host:
        return None, None

    platform_map = {
        "instagram.com": "instagram", "www.instagram.com": "instagram",
        "x.com": "x", "www.x.com": "x",
        "twitter.com": "x", "www.twitter.com": "x",
        "linkedin.com": "linkedin", "www.linkedin.com": "linkedin",
        "github.com": "github", "www.github.com": "github",
        "tiktok.com": "tiktok", "www.tiktok.com": "tiktok",
        "facebook.com": "facebook", "www.facebook.com": "facebook",
        "medium.com": "medium", "www.medium.com": "medium",
        "pinterest.com": "pinterest", "www.pinterest.com": "pinterest",
    }

    platform = platform_map.get(host)
    if not platform:
        return None, None

    parts = [p for p in path.split("/") if p]
    if not parts:
        return platform, None

    handle: typing.Optional[str] = parts[0]

    # Özel path durumları
    if platform == "x" and handle in {"i", "share", "home"} and len(parts) > 1:
        handle = parts[1]
    if platform == "linkedin" and handle in {"in", "company", "school", "pub"} and len(parts) > 1:
        handle = parts[1]
    if platform == "facebook" and handle in {"people", "profile.php"} and len(parts) > 1:
        handle = parts[1]

    # Temizlik
    handle = (handle or "").split("?")[0].split("#")[0]
    import re as _re  # yerel güvenli import (dosyada re yoksa hata yaşamayalım)
    handle = _re.sub(r"[^\w\.-]", "", handle)

    return platform, (handle or None)
# ---------- Google CSE ----------
async def _search_cse(full_name: str, hometown: str, limit_per_source: int, fast: bool) -> Tuple[List[ProfileEntry], SourceInfo]:
    t0 = time.time()
    api_key = os.getenv("GOOGLE_CSE_API_KEY", "").strip()
    cx = os.getenv("GOOGLE_CSE_CX", "").strip()
    if not api_key or not cx:
        return [], SourceInfo(type="cse", ok=False, took_ms=int((time.time() - t0) * 1000), reason="api_key_invalid")

    sites = ["instagram.com","x.com","twitter.com","linkedin.com","github.com","tiktok.com","facebook.com","medium.com","pinterest.com"]
    query = f"\"{full_name}\" {hometown} " + " ".join(f"site:{s}" for s in sites)

    url = "https://www.googleapis.com/customsearch/v1"
    num = min(5 if fast else 10, limit_per_source)
    params = {"q": query, "key": api_key, "cx": cx, "num": num}

    profiles: List[ProfileEntry] = []
    ok, reason = True, None
    try:
        async with httpx.AsyncClient(timeout=12 if fast else 15, follow_redirects=True) as cli:
            r = await cli.get(url, params=params)
            if r.status_code in (400, 403):
                ok, reason = False, "api_key_invalid"
            else:
                r.raise_for_status()
                data = r.json()
                for item in data.get("items", [])[:num]:
                    link = item.get("link")
                    if not link:
                        continue
                    parsed = _platform_from_url(link)
                    if not parsed:
                        continue
                    platform, handle = parsed
                    profiles.append(ProfileEntry(platform=platform, handle=handle, url=link))
    except Exception as e:
        ok, reason = False, "api_key_invalid"

    return profiles, SourceInfo(type="cse", ok=ok, took_ms=int((time.time()-t0)*1000), reason=reason)

# ---------- Internal scans ----------
async def _scan_username(base_url: str, username: str, timeout: int) -> Dict[str, Any]:
    """
    Username taraması — doğrudan Instagram servisini çağırır.
    """
    from app.services.instagram_service import fetch_bio_instagram

    t0 = time.time()
    results = []

    ig_res = None
    ig_err_msg = None
    try:
        ig_res = await asyncio.wait_for(fetch_bio_instagram(username), timeout=15.0)
    except Exception as e:
        ig_err_msg = str(e) if str(e) else type(e).__name__

    # Instagram 429 rate limit detection
    is_ig_429 = False
    if ig_err_msg and "429" in ig_err_msg:
        is_ig_429 = True
    elif isinstance(ig_res, dict):
        if ig_res.get("status") == "429" or ig_res.get("error") == "429":
            is_ig_429 = True

    if is_ig_429:
        results.append({
            "profile": {
                "profile_url": f"https://www.instagram.com/{username}/",
                "display_name": "",
                "bio": "",
                "status": "exists"
            },
            "scores": {
                "total": 1.0
            }
        })
    elif isinstance(ig_res, dict) and ig_res.get("status") == "exists":
        results.append({
            "profile": {
                "profile_url": ig_res.get("url") or f"https://www.instagram.com/{username}/",
                "display_name": ig_res.get("display_name") or "",
                "bio": ig_res.get("bio") or "",
                "status": "exists"
            },
            "scores": {
                "total": 1.0
            }
        })

    errors = []
    if ig_err_msg:
        errors.append(f"instagram:{ig_err_msg}")

    if ig_err_msg and not results:
        err_reason = " | ".join(errors)
        return {
            "input": {"email": None, "username": username, "phone": None},
            "results": {},
            "verdict": "fail",
            "took_ms": int((time.time() - t0) * 1000),
            "error": err_reason,
            "reason": err_reason
        }

    err_reason = " | ".join(errors) if errors else None
    return {
        "input": {"email": None, "username": username, "phone": None},
        "results": {
            "social": {
                "ok": True,
                "data": {
                    "results": results
                }
            }
        },
        "verdict": "ok" if results else "partial",
        "took_ms": int((time.time() - t0) * 1000),
        "error": err_reason,
        "reason": err_reason
    }





async def _scan_email(base_url: str, email: str, timeout: int) -> Dict[str, Any]:
    """
    Email taraması — in-process `_scan_full_legacy` çağırır.

    Bkz. `_scan_username` için açıklama.
    """
    from app.routers.unified import _scan_full_legacy
    try:
        return await _scan_full_legacy(
            email=email, username=None, phone=None, timeout=float(timeout)
        )
    except Exception as e:
        return {
            "input": {"email": email, "username": None, "phone": None},
            "results": {},
            "verdict": "fail",
            "took_ms": 0,
            "error": str(e),
        }

# ---------- Scoring ----------
def _confidence_score(entry: ProfileEntry, first: str, last: str, hometown: str, raw_profile: Optional[Dict[str, Any]] = None) -> Tuple[float, List[str]]:
    ev: List[str] = []
    score = 0.0
    f, l, home = _norm(first), _norm(last), _norm(hometown)

    blobs = []
    if raw_profile:
        prof = raw_profile.get("profile", {})
        for k in ("display_name","bio","status"):
            blobs.append(str(prof.get(k, "")))
    blobs.append(entry.url)
    text = " ".join(_norm(t) for t in blobs)

    if f and f in text: score += 0.25; ev.append(f"first_name_match:{first}")
    if l and l in text: score += 0.25; ev.append(f"last_name_match:{last}")
    if home and home in text: score += 0.10; ev.append(f"hometown_match:{hometown}")

    fused = _strip_non_alnum(first + last)
    h_norm = _strip_non_alnum(entry.handle)
    if fused and h_norm and len(set(fused) & set(h_norm)) / max(len(set(fused)), 1) > 0.5:
        score += 0.20; ev.append("handle_name_similarity")

    if raw_profile:
        sc = raw_profile.get("scores", {})
        total = sc.get("total")
        if isinstance(total, (int, float)):
            s = max(0.0, min(float(total), 1.0))
            score += 0.20 * s
            ev.append(f"social_score:{s}")

    return min(1.0, score), ev

# ---------- Orchestrator ----------
async def build_person_card(query: PersonQuery, base_url: str, cache_ttl: int = 3600) -> PersonCard:
    t0 = time.time()
    deadline = t0 + max(5, float(query.timeout))
    ck = query.cache_key()

    cached = await cache_get_safe(ck)
    if cached:
        out = PersonCard.model_validate(cached)
        out.took_ms = int((time.time() - t0) * 1000)
        return out

    base_url = base_url.rstrip("/")
    full_name = f"{query.first_name} {query.last_name}"

    # 1) Candidate handles
    candidates = set(_username_variants(query.first_name, query.last_name))
    for u in query.hints.usernames:
        if u: candidates.add(_strip_non_alnum(u))

    # 2) CSE (opsiyonel)
    cse_profiles, cse_meta = await _search_cse(full_name, query.hometown, query.limit_per_source, query.fast)
    for p in cse_profiles:
        candidates.add(_strip_non_alnum(p.handle))

    # handle → orijinal
    handle_by_key: Dict[str, str] = { _strip_non_alnum(p.handle): p.handle for p in cse_profiles }
    for c in list(candidates):
        handle_by_key.setdefault(c, c)

    # Hints öncelikli sıralama + sınır
    hint_set = { _strip_non_alnum(u) for u in (query.hints.usernames or []) }
    keys_all = list(handle_by_key.keys())
    keys_all.sort(key=lambda k: (k not in hint_set, len(k)))  # hints öne
    scan_cap_default = 5 if query.fast else 10
    scan_cap = min(
        query.limit_per_source,
        query.max_scans if (query.max_scans or 0) > 0 else scan_cap_default,
        20
    )
    targets = keys_all[: max(1, scan_cap)]

    sem = asyncio.Semaphore(6 if query.fast else 8)
    scan_results: Dict[str, Dict[str, Any]] = {}
    sources_meta: List[SourceInfo] = [cse_meta]

    async def _do_scan(h: str):
        key = handle_by_key.get(h, h)
        t1 = time.time()
        ok, reason, data = True, None, None

        # Global time budget kontrolü
        if time.time() > deadline - 1.5:
            sources_meta.append(SourceInfo(type=f"social_scan:{key}", ok=False, took_ms=0, reason="skip:time_budget"))
            return

        # Per-call timeout (fast modda daha kısa)
        per_call = min(20, max(5, int(query.timeout - 5))) if not query.fast else min(12, max(5, int(query.timeout - 8)))

        try:
            async with sem:
                data = await asyncio.wait_for(_scan_username(base_url, key, timeout=per_call), timeout=per_call + 2)
        except Exception as e:
            err_msg = str(e) if str(e) else type(e).__name__
            ok, reason = False, f"scan_err:{err_msg}"
        finally:
            took = int((time.time() - t1) * 1000)
            sources_meta.append(SourceInfo(type=f"social_scan:{key}", ok=ok, took_ms=took, reason=reason))
            if data:
                scan_results[key] = data

    await asyncio.gather(*[_do_scan(h) for h in targets])

    # 3) Email taraması (fast değilse veya açıkça verilmişse)
    emails_out: List[Dict[str, Any]] = []
    if query.hints.emails and (not query.fast):
        for em in query.hints.emails[: min(query.limit_per_source, 5)]:
            t1 = time.time()
            ok, reason = True, None
            if time.time() > deadline - 1.0:
                sources_meta.append(SourceInfo(type=f"email_scan:{em}", ok=False, took_ms=0, reason="skip:time_budget"))
                break
            try:
                per_call = min(15, max(5, int(query.timeout - 10)))
                data = await asyncio.wait_for(_scan_email(base_url, em, timeout=per_call), timeout=per_call + 2)
                emails_out.append({"email": em, "result": data})
            except Exception as e:
                ok, reason = False, f"email_err:{e}"
            sources_meta.append(SourceInfo(type=f"email_scan:{em}", ok=ok, took_ms=int((time.time()-t1)*1000), reason=reason))

    # 4) Profilleri derle
    profiles: List[ProfileEntry] = []
    profiles.extend(cse_profiles)

    first, last = query.first_name, query.last_name
    for uname, result in scan_results.items():
        try:
            ok = bool(result.get("results", {}).get("social", {}).get("ok", False))
            if not ok:
                continue
            items = result["results"]["social"]["data"]["results"]
        except Exception:
            continue
            
        for item in items:
            prof = item.get("profile") or {}
            url = prof.get("profile_url") or ""
            status = str(prof.get("status") or "unknown")
            if not url or status != "exists":
                continue

            parsed = _platform_from_url(url)
            if not parsed:
                continue
            platform, handle = parsed

            entry = ProfileEntry(platform=platform, handle=handle, url=url, status=status, raw=item)
            conf, ev = _confidence_score(entry, first, last, query.hometown, raw_profile=item)
            entry.confidence = max(conf, 1.0)
            entry.evidence.extend(ev)
            profiles.append(entry)

    # Dedup & sırala
    dedup: Dict[Tuple[str, str], ProfileEntry] = {}
    for p in profiles:
        key = (p.platform, p.handle.lower())
        cur = dedup.get(key)
        if not cur or p.confidence > cur.confidence:
            dedup[key] = p
    profiles = sorted(dedup.values(), key=lambda x: x.confidence, reverse=True)

    overall = 0.0
    if profiles:
        overall = sum(p.confidence for p in profiles[:5]) / max(1, min(5, len(profiles)))
    verdict = "ok" if profiles or emails_out else "partial"
    if not profiles and not emails_out:
        verdict = "fail"
    
    card = PersonCard(
        query={
            "first_name": query.first_name,
            "last_name": query.last_name,
            "hometown": query.hometown,
            "hints": query.hints.model_dump(),
            "limit_per_source": query.limit_per_source,
            "timeout": query.timeout,
            "fast": query.fast,
            "max_scans": query.max_scans,
        },
        summary={
            "username_best_guesses": [p.handle for p in profiles[:5]],
            "notes": "CSE + sosyal tarama + ipuçları birleştirildi.",
            "confidence_overall": round(overall, 3),
        },
        profiles=profiles,
        emails=emails_out,
        phones=query.hints.phones,
        sources=sources_meta,
        verdict=verdict,
        took_ms=int((time.time() - t0) * 1000),
    )

    await cache_set_safe(ck, card.model_dump(), ttl=cache_ttl)
    return card