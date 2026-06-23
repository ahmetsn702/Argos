from fastapi import APIRouter, Query
import httpx, time, re, unicodedata

router = APIRouter(tags=["variants"])
API_BASE = "http://127.0.0.1:8000"

CONNECT_TIMEOUT = 5
READ_TIMEOUT = 60
TIMEOUT = (CONNECT_TIMEOUT, READ_TIMEOUT)

MOJIBAKE_MARK = re.compile(r"[�����]")

def demojibake(s):
    if not s or not isinstance(s, str):
        return s
    # Sadece mojibake belirtisi varsa d�zelt
    if MOJIBAKE_MARK.search(s):
        try:
            return s.encode("latin-1", "ignore").decode("utf-8", "ignore")
        except Exception:
            return s
    return s

def fold(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    return " ".join(s.strip().split())

def tokens(s: str | None):
    return re.findall(r"[a-z0-9g�si��]+", fold(s), flags=re.I)

def trigrams(s: str):
    if not s:
        return set()
    s = s.replace(" ", "_")
    return {s[i:i+3] for i in range(len(s) - 2)} if len(s) >= 3 else {s}

def jaccard(a: str, b: str) -> float:
    A = set(w for w in a.split() if w)
    B = set(w for w in b.split() if w)
    if not A and not B:
        return 0.0
    return len(A & B) / max(1, len(A | B))

def trigram_sim(a: str, b: str) -> float:
    A, B = trigrams(a), trigrams(b)
    if not A and not B:
        return 0.0
    return len(A & B) / max(1, len(A | B))

def smart_score(ig_bio_raw, x_bio_raw, name_hit: bool):
    a = fold(ig_bio_raw)
    b = fold(x_bio_raw)
    j = jaccard(a, b) if (a or b) else 0.0
    t = trigram_sim(a, b) if (a or b) else 0.0
    score = 0.6 * t + 0.4 * j
    name_bonus = 0.15 if name_hit else 0.0
    if name_bonus:
        score = min(1.0, score + name_bonus)
    empty_bio_penalty = 0.0
    if bool(a) ^ bool(b):
        empty_bio_penalty = 0.10
        score = max(0.0, score - empty_bio_penalty)

    verdict = "Low"
    if score >= 0.85:
        verdict = "High"
    elif score >= 0.60:
        verdict = "Medium"

    return {
        "score": score,
        "score_pct": round(score * 100, 2),
        "verdict": verdict,
        "partials": {"jaccard": round(j, 4), "trigram": round(t, 4)},
        "tweaks": {"name_bonus": round(name_bonus, 2), "empty_bio_penalty": round(empty_bio_penalty, 2)},
    }

def ascii_name_combo(display_name: str | None):
    if not display_name:
        return []
    f = fold(display_name)
    parts = [p for p in f.split() if p]
    out = set()
    if len(parts) == 1:
        p = parts[0]
        out |= {p, p[:1], p[:2], p[:3]}
    elif len(parts) >= 2:
        first, last = parts[0], parts[-1]
        out |= {
            first, last,
            f"{first}{last}", f"{first}.{last}", f"{first}_{last}", f"{first}-{last}",
            f"{last}{first}", f"{last}.{first}", f"{last}_{first}", f"{last}-{first}",
            f"{first}.{last[:1]}", f"{first}_{last[:1]}", f"{first}-{last[:1]}",
            f"{first[:1]}.{last}", f"{first[:1]}_{last}", f"{first[:1]}-{last}",
        }
    return [x for x in out if x]

def generate_variants(ig_username: str, display_name: str | None, max_variants: int = 30):
    u = fold(ig_username)

    # 1) IG tabanli: exact + sikistirmalar
    primary = [u]
    comp1 = re.sub(r"(.)\1+", r"\1", u)
    comp2 = re.sub(r"(.)\1+", r"\1", comp1)
    if comp1 != u: primary.append(comp1)
    if comp2 not in primary: primary.append(comp2)

    # 2) Tek karakter silmeler (k���k bir havuz)
    deletions = []
    for i in range(len(u)):
        deletions.append(u[:i] + u[i+1:])

    # 3) Isim kombinasyonlari + varyasyonlar
    namec = ascii_name_combo(display_name)
    extras = set()
    for x in namec:
        x2 = x.replace(" ", "")
        if len(x2) >= 4:
            extras |= {x2, x2 + "_", x2 + "."}

    # �ncelik sirasi korunarak uniq liste
    order = primary + deletions + namec + list(extras)
    seen = set()
    ordered = []
    for it in order:
        if it and it not in seen:
            seen.add(it)
            ordered.append(it)
        if len(ordered) >= max_variants:
            break
    return ordered

def fetch_ig(username: str):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_fetch_ig_async(username))

async def _fetch_ig_async(username: str):
    from app.routers.compat_ui import compare_ig_x
    comp = await compare_ig_x(username)
    if not isinstance(comp, dict):
        try:
            comp = comp.body and __import__("json").loads(comp.body)
        except Exception:
            comp = {}
    ig = comp.get("instagram") or {}
    return {
        "display_name": demojibake(ig.get("display_name")),
        "bio": demojibake(ig.get("bio")),
    }

async def _fetch_x_async(handle: str):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await client.get(
                f"{API_BASE}/username-bios",
                params={"username": handle, "only": "x"}
            )
            r.raise_for_status()
        data = r.json().get("results", [])
        if not data:
            return {"status": "unknown", "display_name": None, "bio": None, "source": None, "url": f"https://x.com/{handle}"}
        x = data[0]
        dn = demojibake(x.get("display_name"))
        st = x.get("status")
        if dn and "page not found" in dn.lower():
            st = "not_found"
        return {
            "status": st,
            "display_name": dn,
            "bio": demojibake(x.get("bio")),
            "source": x.get("source"),
            "url": x.get("url") or f"https://x.com/{handle}",
        }
    except httpx.ReadTimeout:
        return {"status": "timeout", "display_name": None, "bio": None, "source": None, "url": f"https://x.com/{handle}"}
    except Exception:
        return {"status": "error", "display_name": None, "bio": None, "source": None, "url": f"https://x.com/{handle}"}

def fetch_x(handle: str):
    import asyncio
    return asyncio.get_event_loop().run_until_complete(_fetch_x_async(handle))

@router.get("/try-x-variants")
async def try_x_variants(username: str, display_name: str | None = None, max_variants: int = Query(20, ge=1, le=60), throttle_ms: int = Query(300, ge=0)):
    ig = await _fetch_ig_async(username)
    variants = generate_variants(username, display_name or ig.get("display_name"), max_variants=max_variants)

    tried = []
    for h in variants:
        x = await _fetch_x_async(h)
        xd = fold(x.get("display_name"))
        idisp = fold(display_name or ig.get("display_name"))
        name_hit = bool(xd and idisp and (idisp in xd))
        sc = smart_score(ig.get("bio"), x.get("bio"), name_hit)
        tried.append({
            "handle": h,
            "status": x.get("status"),
            "display_name": x.get("display_name"),
            "bio": x.get("bio"),
            "url": x.get("url"),
            "score": sc["score"],
            "score_pct": sc["score_pct"],
            "verdict": sc["verdict"],
            "same_display_name": name_hit,
            "partials": sc["partials"],
            "tweaks": sc["tweaks"],
        })
        if throttle_ms > 0:
            time.sleep(throttle_ms / 1000.0)

    tried_sorted = sorted(tried, key=lambda r: (-r["score"], r["handle"]))
    return {
        "impl": "variants-v3-timeoutsafe+smartorder",
        "ig": {"username": username, "display_name": ig.get("display_name"), "bio": ig.get("bio")},
        "tried": len(tried_sorted),
        "results": tried_sorted,
    }

@router.get("/rank-x-candidates")
async def rank_x_candidates(ig_username: str, display_name: str | None = None, max_variants: int = Query(20, ge=1, le=60), throttle_ms: int = Query(300, ge=0), stop_at_first_good: bool = Query(False)):
    data = await try_x_variants(username=ig_username, display_name=display_name, max_variants=max_variants, throttle_ms=throttle_ms)
    results = data["results"]
    best = results[0] if results else None
    return {
        "impl": "x-linker-v3-timeoutsafe+smartorder",
        "ig": data["ig"],
        "tried": data["tried"],
        "best": best,
        "results": results,
    }
