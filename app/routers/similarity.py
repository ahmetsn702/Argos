# -*- coding: utf-8 -*-
import json, re, unicodedata
from typing import Dict, List, Optional, Set
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse, Response

# Mevcut yardımcılar (proje içinden)
from app.utils.common import normalize_bio_text, tokens, jaccard, char_ngrams, cosine_sim
from app.services.x_fetch import fetch_x_profile_simple
from app.services.instagram_service import get_instagram_bio as fetch_ig_profile_simple

router = APIRouter(tags=["similarity","hunt"])

def _pct(x: float) -> float:
    try: v = float(x)
    except Exception: v = 0.0
    if v < 0: v = 0.0
    if v > 1: v = 1.0
    return round(v * 100.0, 2)

def _name_norm(s: str) -> str:
    s = (s or "").strip().lower()
    s = s.replace("ı","i").replace("İ","i").replace("ş","s").replace("Ş","s") \
         .replace("ğ","g").replace("Ğ","g").replace("ç","c").replace("Ç","c") \
         .replace("ö","o").replace("Ö","o").replace("ü","u").replace("Ü","u")
    return " ".join(s.split())

def _bio_similarity(b1: str, b2: str) -> Dict[str, float]:
    t1, t2 = tokens(b1), tokens(b2)
    j, inter, a_cnt, b_cnt = jaccard(t1, t2)
    c = cosine_sim(char_ngrams(b1, 3), char_ngrams(b2, 3))
    score = 0.6 * j + 0.4 * c
    return {
        "jaccard_raw": j,
        "char_trigram_raw": c,
        "score_raw": score,
        "token_intersection": inter,
        "tokens_a": a_cnt,
        "tokens_b": b_cnt,
    }

@router.get("/compare-ig-x2")
async def compare_ig_x2(username: str = Query(..., min_length=1),
                  display_name_hint: Optional[str] = Query(None)):
    uname = username.strip().lstrip("@")

    ig = await fetch_ig_profile_simple(uname) or {
        "status":"unknown","username":uname,"display_name":"",
        "bio":"","profile_url":f"https://instagram.com/{uname}"
    }
    xt = await fetch_x_profile_simple(uname) or {
        "status":"unknown","username":uname,"display_name":"",
        "bio":"","profile_url":f"https://x.com/{uname}"
    }

    b1 = normalize_bio_text(ig.get("bio","") or "")
    b2 = normalize_bio_text(xt.get("bio","") or "")
    sim = _bio_similarity(b1, b2)

    name_bonus = 0.0
    same_display = False
    if ig.get("display_name") and xt.get("display_name"):
        same_display = (_name_norm(ig["display_name"]) == _name_norm(xt["display_name"]))
        if same_display: name_bonus += 0.15

    same_username_bonus = 0.0
    if ig.get("status") != "exists" and xt.get("status") == "exists":
        same_username_bonus += 0.30

    hint_bonus = 0.0
    if display_name_hint and xt.get("display_name"):
        if _name_norm(display_name_hint) == _name_norm(xt["display_name"]):
            hint_bonus += 0.20

    empty_bio_penalty = 0.0
    if not b1 or not b2:
        empty_bio_penalty += 0.10

    score = sim["score_raw"] + name_bonus + same_username_bonus + hint_bonus - empty_bio_penalty
    score = max(0.0, min(1.0, score))

    verdict = "Low"
    if score >= 0.70: verdict = "High"
    elif score >= 0.40: verdict = "Medium"

    out = {
        "impl": "smartscore-v1.1",
        "instagram": ig,
        "x_twitter": xt,
        "similarity": {
            "jaccard_pct": _pct(sim["jaccard_raw"]),
            "char_trigram_pct": _pct(sim["char_trigram_raw"]),
            "score_pct": _pct(score),
            "score_raw": round(score, 4),
            "jaccard_raw": round(sim["jaccard_raw"], 4),
            "char_trigram_raw": round(sim["char_trigram_raw"], 4),
            "token_intersection": sim["token_intersection"],
            "tokens_a": sim["tokens_a"],
            "tokens_b": sim["tokens_b"],
            "same_display_name": same_display,
            "verdict": verdict,
            "tweaks": {
                "name_bonus": round(name_bonus, 3),
                "same_username_bonus": round(same_username_bonus, 3),
                "hint_bonus": round(hint_bonus, 3),
                "empty_bio_penalty": round(empty_bio_penalty, 3),
            },
        },
    }
    return Response(content=json.dumps(out, ensure_ascii=False),
                    media_type="application/json; charset=utf-8")

# --------- HUNT: X'i isimden bul (ASCII handle üretimi) ---------

def _fold_tr(s: str) -> str:
    # Türkçe karakterleri ASCII'ye katla + diakritikleri temizle
    s = (s or "").translate(str.maketrans("ıİşŞğĞçÇöÖüÜ", "iissggccoouu"))
    s = unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not unicodedata.combining(c))

def _norm_text(s: str) -> str:
    s = _fold_tr((s or "").lower())
    s = re.sub(r"[^a-z0-9]+", " ", s).strip()
    return s

def _no_vowels(s: str) -> str:
    return re.sub(r"[aeiou]", "", s or "")

def _double_last(s: str) -> str:
    return s + s[-1] if s else s

def _double_first(s: str) -> str:
    return (s[0]*2 + s[1:]) if s else s

def _consonant_skeleton(s: str) -> str:
    return re.sub(r"[aeiou]", "", s or "")

def _sanitize_x(u: str) -> str:
    # X: sadece a-z0-9_ ; noktaları '_' yap, diğerlerini at
    u = _fold_tr((u or "").lower()).replace(".", "_")
    u = re.sub(r"[^a-z0-9_]", "", u)
    return u

def _gen_username_candidates(full_name: str, limit: int = 25) -> List[str]:
    base: Set[str] = set()
    toks = [t for t in re.findall(r"[A-Za-zĞÜŞİÖÇğüşıöç]+", full_name or "")]
    toks = [_fold_tr(t).lower() for t in toks if t]
    if not toks: return []
    first = toks[0]
    last  = toks[-1] if len(toks) > 1 else ""

    last_short  = _no_vowels(last)  or last
    first_short = _no_vowels(first) or first

    base.update({
        first+last, first+"_"+last, first+"."+last,
        first+last_short, first_short+last_short,
        (first[0]+last) if first else "",
        (first[:2]+last) if len(first)>=2 else "",
        last+first,
    })

    f_vars = {first, _double_last(first)}
    l_vars = {last, last_short,
              _double_first(last) if last else last,
              _double_first(last_short) if last_short else last_short}
    for fv in f_vars:
        for lv in l_vars:
            if fv and lv:
                base.add(fv+lv)

    if first.endswith("t"):
        base.add(first + "t" + last_short)
    if last_short.startswith("s"):
        base.add(first + "s" + last_short)
        base.add(_double_last(first) + last_short)
        base.add(_double_last(first) + "s" + last_short)

    base.add(_consonant_skeleton(first) + _consonant_skeleton(last or last_short))

    # === KRİTİK: ASCII + _ filtrele, boşları ve çok kısa/uzunları at ===
    base = {_sanitize_x(u) for u in base}
    cands = [u for u in base if u and re.fullmatch(r"[a-z0-9_]{3,30}", u)]
    # Sıralama: kısa ve "first...last_short" uyumlu olanlar öne
    def _rank(u: str) -> tuple:
        score = 0
        if "tt" in u: score -= 1
        if "ss" in u: score -= 1
        if u.startswith(first): score -= 0.5
        if u.endswith(last_short): score -= 0.5
        return (score, len(u))
    cands.sort(key=_rank)
    return cands[:limit]

def _score_profile(profile: Dict, full_name: str, keywords: List[str]) -> Dict[str, float]:
    disp = _norm_text(profile.get("display_name", ""))
    target = _norm_text(full_name)
    name_score = 0.0
    if disp and target:
        if disp == target:
            name_score = 1.0
        else:
            parts = [p for p in target.split() if p]
            hits = sum(1 for p in parts if p in disp)
            if hits >= 2: name_score = 1.0
            elif hits == 1: name_score = 0.7
            else: name_score = 0.4 if (parts and parts[0] in disp) else 0.0

    bio_n = _norm_text(profile.get("bio", ""))
    kws_n = [_norm_text(k) for k in (keywords or []) if k]
    kw_hits = sum(1 for k in kws_n if (k and k in bio_n))
    kw_score = (kw_hits / len(kws_n)) if kws_n else 0.0

    total = round(0.7 * name_score + 0.3 * kw_score, 4)
    return {"name_score": name_score, "keyword_hits": kw_hits,
            "keyword_score": kw_score, "total": total}

@router.get("/hunt-x-by-name")
async def hunt_x_by_name(
    full_name: str = Query(..., min_length=2),
    kw: List[str] = Query(default=[]),
    limit: int = Query(default=20, ge=1, le=50),
    stop_at: float = Query(default=0.92)
):
    candidates = _gen_username_candidates(full_name, limit=limit)
    results, tried = [], 0
    for u in candidates:
        tried += 1
        prof = await fetch_x_profile_simple(u) or {
            "status":"unknown","username":u,"display_name":"",
            "bio":"","profile_url":f"https://x.com/{u}"
        }
        sc = _score_profile(prof, full_name, kw)
        results.append({"username": u, "profile": prof, "scores": sc})
        if sc["total"] >= stop_at:
            break

    results.sort(key=lambda r: r["scores"]["total"], reverse=True)
    return JSONResponse({
        "full_name": full_name, "keywords": kw,
        "candidates_tried": tried, "results": results
    })
