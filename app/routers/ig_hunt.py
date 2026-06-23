# app/routers/hunt_social.py
# -*- coding: utf-8 -*-

import re
import unicodedata
from typing import List, Dict

from fastapi import APIRouter, Query
from fastapi.responses import Response, JSONResponse

from app.services.instagram_service import get_instagram_bio as get_instagram_profile

router = APIRouter(tags=["ig"])

# ------------------------------
# utils
# ------------------------------

def _strip_diacritics(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))

def _no_vowels(s: str) -> str:
    return re.sub(r"[aeiou]", "", s)

def _norm_tokens_from_name(full_name: str) -> List[str]:
    toks = re.findall(r"[A-Za-zÄÃœÅÄ°Ã–Ã‡ÄŸÃ¼ÅŸÄ±Ã¶Ã§]+", full_name or "")
    toks = [_strip_diacritics(t).lower() for t in toks if t]
    return toks

# ------------------------------
# candidate generator
# ------------------------------

def _gen_ig_candidates(full_name: str, limit: int = 40) -> List[str]:
    toks = _norm_tokens_from_name(full_name)
    if not toks:
        return []

    first = toks[0]
    last  = toks[-1] if len(toks) > 1 else ""
    last_short  = _no_vowels(last) or last
    first_short = _no_vowels(first) or first

    base = {
        # klasik
        first + last,
        first + "." + last,
        first + "_" + last,
        # kÄ±sa soyad
        first + last_short,
        first + "." + last_short,
        first + "_" + last_short,
        # ters
        last + first,
        # tek parÃ§a adaylar
        first,
        last,
        # baÅŸka kombin
        first_short + last,
        first_short + last_short,
    }

    # first 't' ile bitiyorsa "ahmett" varyasyonlarÄ±
    if first.endswith("t"):
        base.update({
            first + "t" + last_short,
            first + "t." + last_short,
            first + "t_" + last_short,
        })

    # last_short 's' ile baÅŸlÄ±yorsa "ssyn" varyasyonlarÄ±
    if last_short.startswith("s"):
        base.update({
            first + "s" + last_short,
            first + ".s" + last_short,
            first + "_s" + last_short,
        })
        if first.endswith("t"):
            base.update({
                first + "t" + "s" + last_short,
                first + "t.s" + last_short,
                first + "t_s" + last_short,
            })

    # nokta/altÃ§izgi IGâ€™de yaygÄ±n â€” minik sÄ±ralama sinyali
    cands = [u for u in base if u]
    def _rank(u: str) -> tuple[int, int]:
        score = 0
        if "." in u: score -= 1
        if "_" in u: score -= 1
        return (score, len(u))

    cands.sort(key=_rank)
    return cands[:limit]

# ------------------------------
# scoring
# ------------------------------

def _score_ig(profile: Dict, full_name: str, keywords: List[str]) -> Dict[str, float]:
    def n(s: str) -> str:
        s = _strip_diacritics((s or "").lower())
        return re.sub(r"[^a-z0-9 ]+", " ", s).strip()

    disp   = n(profile.get("display_name", ""))
    target = n(full_name)

    # 1) display_name bazlÄ± eÅŸleÅŸme
    name_score = 0.0
    if disp and target:
        if disp == target:
            name_score = 1.0
        else:
            parts = [p for p in target.split() if p]
            hits  = sum(1 for p in parts if p in disp)
            if hits >= 2:
                name_score = 1.0
            elif hits == 1:
                name_score = 0.7
            else:
                # sadece ad tutuyorsa hafif sinyal
                name_score = 0.6 if (parts and parts[0] in disp) else 0.0

    # 2) bio anahtar kelime sinyali
    bio_n  = n(profile.get("bio", ""))
    kws_n  = [n(k) for k in keywords if k]
    kw_hits   = sum(1 for k in kws_n if (k and k in bio_n))
    kw_score  = (kw_hits / len(kws_n)) if kws_n else 0.0

    # 3) USERNAME HEURISTIC (bio/isim boÅŸsa devreye girsin)
    #    - Ahmet SayÄ±n -> first='ahmet', last_short='syn'
    #    - 'ahmett?[\._]?s?syn' gibi gÃ¼Ã§lÃ¼ varyasyonlarÄ± 1.0 kabul ediyoruz
    uname = (profile.get("username") or "").lower()
    toks  = _norm_tokens_from_name(full_name)
    if toks:
        first = toks[0]
        last  = toks[-1] if len(toks) > 1 else ""
        last_short = _no_vowels(last) or last

        # Genel (iki parÃ§alÄ±) kalÄ±plar
        patterns = [
            rf"^{re.escape(first)}{re.escape(last)}$",
            rf"^{re.escape(first)}[\._]?{re.escape(last)}$",
            rf"^{re.escape(first)}{re.escape(last_short)}$",
            rf"^{re.escape(first)}[\._]?{re.escape(last_short)}$",
        ]

        # 'ahmet' â†’ 'ahmett' (opsiyonel fazladan t)
        if first.endswith("t") and last_short:
            # optional extra 't' + optional '.' or '_' + optional extra 's' before last_short
            patterns.append(
                rf"^{re.escape(first)}t?[\._]?s?{re.escape(last_short)}$"
            )
        elif last_short:
            patterns.append(
                rf"^{re.escape(first)}[\._]?s?{re.escape(last_short)}$"
            )

        # EÅŸleÅŸiyorsa, name_score en az 1.0 olsun (kw yoksa total â‰ˆ 0.7)
        if uname and any(re.search(pat, uname) for pat in patterns):
            name_score = max(name_score, 1.0)

    total = round(0.7 * name_score + 0.3 * kw_score, 4)
    return {
        "name_score": name_score,
        "keyword_hits": kw_hits,
        "keyword_score": kw_score,
        "total": total,
    }

# ------------------------------
# endpoints
# ------------------------------

# NOTE: The canonical `/ig-profile` route is served by
# `app.routers.hunt_social` (which also owns the active `/hunt-ig-by-name`
# and `/v2/hunt-ig-by-name` endpoints). This v1 variant is kept reachable at
# `/ig-profile-v1` for callers that need the explicit
# `Response(ensure_ascii=False)` Turkish-character preservation behaviour.
@router.get("/ig-profile-v1")
async def ig_profile(username: str = Query(..., min_length=1)):
    uname = (username or "").strip().lstrip("@")
    prof = await get_instagram_profile(uname)
    return Response(
        content=__import__("json").dumps(prof, ensure_ascii=False),
        media_type="application/json; charset=utf-8"
    )

