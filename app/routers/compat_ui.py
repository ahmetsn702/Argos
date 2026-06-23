from fastapi import APIRouter
import httpx, unicodedata, re, json, os

router = APIRouter(tags=["compat-ui"])
API_BASE = "http://127.0.0.1:8000"

def fold(s: str | None) -> str:
    if not s:
        return ""
    s = unicodedata.normalize("NFKD", s)
    s = "".join(ch for ch in s if not unicodedata.combining(ch))
    s = s.casefold()
    return " ".join(s.strip().split())

TOKEN_RE = re.compile(r"[a-z0-9ğüşiöç]+", re.I)
GENERIC = {
    "ogrenci","student","developer","dev","engineer","muhendis","yazilim",
    "software","computer","it","tech","technology","coder","coding",
    "merhaba","hello","selam","hi"
}

def tokens(s: str | None):
    return TOKEN_RE.findall(s or "")

def is_generic_bio(raw: str | None) -> bool:
    t = [w for w in tokens(fold(raw)) if len(w) >= 3]
    if not t or len(t) <= 2:
        return True
    g = [w for w in t if w in GENERIC]
    return len(g) >= max(1, int(len(t) * 0.7))

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

def name_token_sim(a: str | None, b: str | None) -> float:
    # İsim benzerliği için token-jaccard (daha sağlam)
    A = set(tokens(fold(a)))
    B = set(tokens(fold(b)))
    if not A and not B:
        return 0.0
    return len(A & B) / max(1, len(A | B))

async def fetch_instagram_profile(username: str):
    status, display, bio = "unknown", None, None
    mobile_ua = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    sessionid = (os.getenv("IG_SESSIONID") or "").strip()
    try:
        h = {
            "User-Agent": mobile_ua,
            "X-IG-App-ID": "936619743392459",
            "Accept": "*/*",
            "Referer": f"https://www.instagram.com/{username}/",
        }
        h["Cookie"] = f"sessionid={sessionid}" if sessionid else "ig_nrcb=1"
        async with httpx.AsyncClient(headers=h, timeout=20, follow_redirects=True) as client:
            r = await client.get(
                "https://i.instagram.com/api/v1/users/web_profile_info/",
                params={"username": username},
            )
            if r.status_code == 200:
                user = r.json().get("data", {}).get("user", {}) or {}
                if user:
                    display = user.get("full_name")
                    bio = user.get("biography") or user.get("bio")
                    return "exists", display, bio
            elif r.status_code == 404:
                return "not_found", None, None

            h2 = {"User-Agent": mobile_ua, "Accept": "text/html", "Referer": "https://www.instagram.com/"}
            r2 = await client.get(f"https://www.instagram.com/{username}/", headers=h2)
            if r2.status_code == 200 and r2.text:
                m = re.search(r'"biography":"(.*?)"', r2.text)
                if m:
                    bio = json.loads(f'"{m.group(1)}"')
                m2 = re.search(r'"full_name":"(.*?)"', r2.text)
                if m2:
                    display = json.loads(f'"{m2.group(1)}"')
                return "exists", display, bio
            elif r2.status_code == 404:
                return "not_found", None, None
    except Exception:
        pass

    return status, display, bio

@router.get("/compare-ig-x")
async def compare_ig_x(username: str, ig_bio_override: str | None = None, x_bio_override: str | None = None):
    # X verisi
    x_display, x_bio_real, x_status = None, None, "unknown"
    try:
        async with httpx.AsyncClient(timeout=30) as client:
            r = await client.get(f"{API_BASE}/username-bios", params={"username": username, "only": "x"})
            r.raise_for_status()
        res = r.json().get("results", [])
        if res:
            x_status = res[0].get("status") or "unknown"
            x_display = res[0].get("display_name")
            x_bio_real = res[0].get("bio")
    except Exception:
        pass

    # IG verisi (override yoksa otomatik çek)
    if ig_bio_override:
        ig_status, ig_display, ig_bio_real = "manual", None, ig_bio_override
    else:
        ig_status, ig_display, ig_bio_real = await fetch_instagram_profile(username)

    # Benzerlik
    a_raw = ig_bio_override or ig_bio_real
    b_raw = x_bio_override if (x_bio_override is not None) else (x_bio_real or None)
    a = fold(a_raw)
    b = fold(b_raw)

    j = jaccard(a, b) if (a or b) else 0.0
    t = trigram_sim(a, b) if (a or b) else 0.0
    score = 0.6 * t + 0.4 * j

    # İsim bonusu: display name benzerliği + bio içinde ad geçmesi
    name_bonus = 0.0
    same_display_name = False
    igd = fold(ig_display)
    xd  = fold(x_display)
    if igd and xd:
        sim_names = max(trigram_sim(igd, xd), name_token_sim(igd, xd))
        if sim_names >= 0.85:
            same_display_name = True
    bio_contains_name = False
    if igd:
        bio_contains_name = igd in a or igd in b
    if xd:
        bio_contains_name = bio_contains_name or xd in a or xd in b

    name_match = same_display_name or bio_contains_name
    if name_match:
        name_bonus = 0.15
        if a and b and (not is_generic_bio(a_raw)) and (not is_generic_bio(b_raw)):
            name_bonus += 0.05
        score = min(1.0, score + name_bonus)

    # Biyolardan biri boşsa ceza (−0.10)
    empty_bio_penalty = 0.0
    if bool(a) ^ bool(b):
        empty_bio_penalty = 0.10
        score = max(0.0, score - empty_bio_penalty)

    # Eşikler
    verdict = "Unknown"
    if a or b or xd or igd:
        if score >= 0.85:
            verdict = "High"
        elif score >= 0.60:
            verdict = "Medium"
        else:
            verdict = "Low"

    return {
        "impl": "smartscore-v1.1",
        "instagram": {"status": ig_status, "display_name": ig_display, "bio": ig_bio_real},
        "x_twitter": {"status": x_status, "display_name": x_display,
                      "bio": x_bio_real if (x_bio_override is None) else x_bio_override},
        "similarity": {
            "jaccard": round(j, 4),
            "trigram": round(t, 4),
            "score_pct": round(score * 100, 2),
            "verdict": verdict,
            "same_display_name": same_display_name,
            "tweaks": {"name_bonus": round(name_bonus, 2), "empty_bio_penalty": round(empty_bio_penalty, 2)},
        },
    }
