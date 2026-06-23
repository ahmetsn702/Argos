# -*- coding: utf-8 -*-
import re, unicodedata
from typing import List, Dict, Tuple
from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse

from app.services.instagram_service import get_instagram_bio as get_instagram_profile

# V2 router: ayrı prefix ile gelir; v1 ile çakışmaz
router = APIRouter(prefix="/v2", tags=["ig"])

# ----------------- Helpers -----------------
_TR_MAP = str.maketrans("ıİşŞğĞçÇöÖüÜ", "iissggccoouu")

def _strip_diacritics(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    return "".join(c for c in s if not unicodedata.combining(c))

def _fold_tr(s: str) -> str:
    s = (s or "").translate(_TR_MAP)
    s = _strip_diacritics(s)
    return (s or "").lower().strip()

def _norm_text(s: str) -> str:
    s = _fold_tr(s)
    return re.sub(r"[^a-z0-9]+", " ", s).strip()

def _no_vowels(s: str) -> str:
    return re.sub(r"[aeiou]", "", s or "")

def _sanitize_ig(u: str) -> str:
    u = _fold_tr((u or "")).replace(" ", "")
    return re.sub(r"[^a-z0-9._]", "", u)

def _uname_core(u: str) -> str:
    # nokta/altçizgi at; fuzzy için çekirdek
    return re.sub(r"[._]+", "", _sanitize_ig(u))

def _skeleton(u: str) -> str:
    return re.sub(r"[aeiou._]", "", _sanitize_ig(u))

# ------------- Fuzzy (Jaro–Winkler) -------------
def _jaro(s1: str, s2: str) -> float:
    s1, s2 = s1 or "", s2 or ""
    if not s1 and not s2: return 1.0
    if not s1 or not s2:  return 0.0
    m_dist = max(len(s1), len(s2))//2 - 1
    m1 = [False]*len(s1); m2 = [False]*len(s2)
    matches = 0
    for i,c in enumerate(s1):
        a = max(0, i - m_dist); b = min(i + m_dist + 1, len(s2))
        for j in range(a,b):
            if not m2[j] and s2[j] == c:
                m1[i] = m2[j] = True
                matches += 1
                break
    if matches == 0: return 0.0
    t = 0; k = 0
    for i in range(len(s1)):
        if m1[i]:
            while not m2[k]: k += 1
            if s1[i] != s2[k]: t += 1
            k += 1
    return (matches/len(s1) + matches/len(s2) + (matches - t/2)/matches)/3.0

def _jaro_winkler(s1: str, s2: str, p: float = 0.1) -> float:
    j = _jaro(s1, s2)
    l = 0
    for a,b in zip(s1, s2):
        if a == b: l += 1
        else: break
        if l == 4: break
    return j + l * p * (1 - j)

# ------------- Username Patterns -------------
def _username_patterns(first: str, last: str) -> List[re.Pattern]:
    f = _fold_tr(first); l = _fold_tr(last)
    fs = _no_vowels(f) or f
    ls = _no_vowels(l) or l
    pats = [
        rf"^{re.escape(f)}t?[\._]?s?{re.escape(ls)}$",
        rf"^{re.escape(f)}t{re.escape(ls)}$",
        rf"^{re.escape(f)}[\._]{re.escape(ls)}$",
        rf"^{re.escape(f)}[\._]?s{re.escape(ls)}$",
        rf"^{re.escape(f)}t[\._]?s{re.escape(ls)}$",
        rf"^{re.escape(f)}t?{re.escape(ls)}$",
        rf"^{re.escape(f)}{re.escape(l)}$",
        rf"^{re.escape(f)}[\._]{re.escape(l)}$",
        rf"^{re.escape(f)}_{re.escape(l)}$",
        rf"^{re.escape(f)}{re.escape(ls)}$",
        rf"^{re.escape(fs)}{re.escape(ls)}$",
        rf"^{re.escape(l)}{re.escape(f)}$",
        rf"^{re.escape(f)}$",
        rf"^{re.escape(fs)}$",
        rf"^{re.escape(f)}[\._]?{re.escape(fs)}$",
    ]
    seen = []
    for p in pats:
        if p not in seen: seen.append(p)
    return [re.compile(p) for p in seen]

# ------------- Candidate Generator -------------
def _split_name(full_name: str) -> Tuple[str, List[str], str]:
    # first, middles, last
    toks_raw = [t for t in re.findall(r"[A-Za-zĞÜŞİÖÇğüşıöç]+", full_name or "")]
    toks = [_fold_tr(t) for t in toks_raw if t]
    if not toks: return "", [], ""
    if len(toks) == 1: return toks[0], [], ""
    return toks[0], toks[1:-1], toks[-1]

def _gen_ig_candidates(full_name: str, limit: int = 60, allow_digits: bool = True) -> List[str]:
    f, mids, l = _split_name(full_name)
    if not f: return []
    fs, ls = _no_vowels(f) or f, _no_vowels(l) or l
    mid = mids[0] if mids else ""
    ms = _no_vowels(mid) or mid

    base = {
        f"{f}{l}", f"{f}.{l}", f"{f}_{l}",
        f"{f}{ls}", f"{fs}{ls}", f"{l}{f}",
        f, l, f"{fs}{l}", f"{f}.{ls}", f"{fs}.{ls}",
        f"{f}t{ls}", f"{f}t.{ls}", f"{f}t_{ls}",
        f"{f}s{ls}", f"{f}.s{ls}", f"{f}_s{ls}",
        f"{f}ts{ls}", f"{f}t.s{ls}", f"{f}t_s{ls}",
    }
    if mid:
        base |= {
            f"{f}{mid}{l}", f"{f}.{mid}.{l}", f"{f}_{mid}_{l}",
            f"{f}{ms}{ls}", f"{fs}{ms}{ls}"
        }

    # sep değişimleri
    more = set()
    for u in list(base):
        if "." in u: more.add(u.replace(".", "_"))
        if "_" in u: more.add(u.replace("_", "."))
    base |= more

    # Rakam opsiyonu: 01..24 eklemeleri (kısa bir varyasyon)
    if allow_digits:
        extra = set()
        for u in base:
            for d in ("", "1", "01", "07", "10", "11", "12", "13", "24"):
                if d:
                    extra.add(f"{u}{d}")
        base |= extra

    # IG kuralları ve uzunluk
    base = {_sanitize_ig(u) for u in base}
    cands = [u for u in base if u and re.fullmatch(r"[a-z0-9._]{2,30}", u)]

    # sıralama: kısa + iskelet uyumu + baş/son uyumu
    fsk, lsk = _skeleton(f), _skeleton(l)
    def _rank(u: str):
        score = 0.0
        core = _uname_core(u)
        usk = _skeleton(u)
        if "." in u: score -= 0.4
        if "_" in u: score -= 0.3
        if u.startswith(f): score -= 0.3
        if u.endswith(ls): score -= 0.3
        # iskelet eşleşmeleri
        if usk.startswith(fsk): score -= 0.2
        if lsk and usk.endswith(lsk): score -= 0.2
        return (score, len(u), u)
    cands.sort(key=_rank)
    return cands[:limit]

# ------------- Scoring -------------
def _score_candidate(username: str, full_name: str, keywords: List[str], neg_keywords: List[str], profile: Dict):
    f, mids, l = _split_name(full_name)
    fs, ls = _no_vowels(f) or f, _no_vowels(l) or l
    uname = _sanitize_ig(username)
    core = _uname_core(uname)

    # A) pattern bazlı isim skoru
    name_score = 0.0
    if any(p.search(uname) for p in _username_patterns(f, l)):
        name_score = 1.0
    else:
        classic = {f"{f}{l}", f"{f}.{l}", f"{f}_{l}", f"{f}{ls}", f"{fs}{ls}", f"{l}{f}"}
        if uname in classic:
            name_score = 0.85
        elif uname.startswith(f) and uname.endswith(ls):
            name_score = 0.75
        elif uname.startswith(f) or uname.endswith(ls):
            name_score = 0.65

    # B) skeleton uyumu
    sk_u = _skeleton(uname)
    sk_t = _skeleton(f + l)
    sk_score = 1.0 if (sk_t and (sk_u.startswith(_skeleton(f)) and sk_u.endswith(_skeleton(l)))) else 0.0

    # C) fuzzy (jaro-winkler) – nokta/altçizgi atılmış çekirdekte
    target_core = _uname_core(f + l)
    fuzzy = _jaro_winkler(core, target_core) if (core and target_core) else 0.0

    # D) keyword – bio, display_name ve username
    bio = _norm_text(profile.get("bio", "") or "")
    disp = _norm_text(profile.get("display_name", "") or "")
    uname_n = _norm_text(uname)
    kws = [_norm_text(k) for k in (keywords or []) if k]
    kw_hits = 0
    for k in kws:
        if not k: continue
        if k in bio or k in disp or k in uname_n: kw_hits += 1
    kw_score = (kw_hits/len(kws)) if kws else 0.0

    # E) negatif keyword cezası
    negs = [_norm_text(k) for k in (neg_keywords or []) if k]
    neg_hit = 0
    for k in negs:
        if not k: continue
        if k in bio or k in disp or k in uname_n: neg_hit += 1
    neg_pen = min(0.5, 0.25 * neg_hit)  # her negatif ~0.25 ceza, max 0.5

    # Toplam skor (ağırlıklar): isim 0.55, skeleton 0.10, fuzzy 0.15, kw 0.25 – ceza
    total = 0.55*name_score + 0.10*sk_score + 0.15*fuzzy + 0.25*kw_score - neg_pen
    total = max(0.0, min(1.0, round(total, 4)))

    return {
        "name_score": round(name_score, 4),
        "skeleton_score": round(sk_score, 4),
        "fuzzy_jw": round(fuzzy, 4),
        "keyword_hits": kw_hits,
        "keyword_score": round(kw_score, 4),
        "neg_hits": neg_hit,
        "neg_penalty": round(neg_pen, 4),
        "total": total,
    }

# ----------------- Endpoints -----------------
# /v2/ig-profile → app/routers/instagram.py'e taşındı

@router.get("/_old/hunt-ig-by-name")
async def hunt_ig_by_name_v2(
    full_name: str = Query(..., min_length=2),
    kw: List[str] = Query(default=[]),
    limit: int = Query(default=60, ge=1, le=100),
    stop_at: float = Query(default=0.92),
    allow_digits: int = Query(default=1, ge=0, le=1),
    debug: int = Query(default=0, ge=0, le=1),
):
    # kw paramında '!' ile başlayanlar negatif kabul edilir
    pos_kw = [k for k in kw if not (k or "").startswith("!")]
    neg_kw = [k[1:] for k in kw if (k or "").startswith("!")]

    cands = _gen_ig_candidates(full_name, limit=limit, allow_digits=bool(allow_digits))
    results: List[Dict] = []
    tried = 0

    for u in cands:
        tried += 1
        prof = await get_instagram_profile(u)
        sc = _score_candidate(u, full_name, pos_kw, neg_kw, prof)
        item = {"username": u, "profile": prof, "scores": sc}
        if debug:
            item["debug"] = {
                "core": _uname_core(u),
                "skeleton": _skeleton(u),
            }
        results.append(item)
        if sc["total"] >= stop_at:
            break

    results.sort(key=lambda r: r["scores"]["total"], reverse=True)
    payload = {
        "full_name": full_name,
        "keywords": pos_kw,
        "neg_keywords": neg_kw,
        "candidates_tried": tried,
        "results": results
    }
    if debug:
        payload["generated"] = cands
    return JSONResponse(payload)

