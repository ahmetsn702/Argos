# -*- coding: utf-8 -*-
import os, re, httpx, collections
from urllib.parse import urljoin, urlparse, parse_qs, unquote
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,tr;q=0.8"}
BASE_MBASIC = "https://mbasic.facebook.com"

def _cookie_header():
    try:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "secrets"))
        path = os.path.join(base, "fb.cookie")
        if not os.path.exists(path): return ""
        s = open(path, "r", encoding="utf-8").read().strip()
        if s.lower().startswith("cookie:"): s = s.split(":",1)[1].strip()
        return s
    except Exception:
        return ""

async def _get(url, timeout=20):
    try:
        h = dict(HEADERS)
        ch = _cookie_header()
        if ch: h["Cookie"] = ch
        if "facebook.com" in url:
            h.setdefault("Referer", "https://m.facebook.com/")
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, headers=h, follow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR:{e!r}"

def _host_ok(u: str) -> bool:
    try: host = urlparse(u).netloc.lower()
    except Exception: return False
    if host.startswith("scontent") or "scontent." in host: return True
    if "lookaside.fbsbx.com" in host or "platform-lookaside.fbsbx.com" in host: return True
    return False

def _strip_query(u: str) -> str:
    try:
        pr = urlparse(u)
        return pr._replace(query="").geturl()
    except Exception:
        return u

def _safe_image_unwrap(src: str) -> str:
    if "safe_image.php" in src:
        try:
            u = parse_qs(urlparse(src).query).get("url",[None])[0]
            if u: return unquote(u)
        except Exception: pass
    return src

def _likely_photo(u: str) -> bool:
    try:
        if not _host_ok(u): return False
        pu = _strip_query(u)
        path = urlparse(pu).path.lower()
        if "/rsrc.php" in path or "/assets.php" in path:
            return False
        ext = os.path.splitext(path)[1].lower()
        if ext in (".jpg", ".jpeg", ".jfif", ".webp", ".gif", ".png"):
            # png/gif bazen ikon; üst katmanda boyuta göre elenir, burada serbest bırak.
            return True
        # uzantısız scontent için tolerans:
        return "scontent" in urlparse(u).netloc.lower()
    except Exception:
        return False

def _is_small(img) -> bool:
    w = img.get("width"); h = img.get("height")
    try: w = int(w)
    except Exception: w = None
    try: h = int(h)
    except Exception: h = None
    mx = max([v for v in (w,h) if isinstance(v,int)], default=None)
    return (mx is not None) and (mx < 120)

def _extract_imgs_from_html(html: str, base_url: str):
    soup = BeautifulSoup(html, "html.parser")
    urls, seen, out = [], set(), []
    og = soup.find("meta", attrs={"property":"og:image"})
    if og and og.get("content"):
        u = _safe_image_unwrap(og["content"])
        if _likely_photo(u): urls.append(u)
    for img in soup.find_all("img", src=True):
        if _is_small(img): continue
        src = _safe_image_unwrap(img["src"])
        if not src: continue
        full = src if src.startswith("http") else urljoin(base_url, src)
        if _likely_photo(full): urls.append(full)
    for u in urls:
        if u not in seen:
            out.append({"url": u, "page": base_url, "source": "fb-page"})
            seen.add(u)
    return out

DETAIL_PATTERNS = (
    "photo.php", "view_full_size", "/photo/?fbid=", "story.php", "story_fbid=",
    "/media/set?", "/albums/", "/profile/picture/view", "/photos/", "set=a."
)

def _find_detail_links(html: str):
    soup = BeautifulSoup(html, "html.parser")
    links = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        if any(p in href for p in DETAIL_PATTERNS):
            links.append(href)
    uniq, seen = [], set()
    for l in links:
        full = l if l.startswith("http") else urljoin(BASE_MBASIC, l)
        if full not in seen:
            uniq.append(full); seen.add(full)
    return uniq

def _find_pagination_links(html: str):
    soup = BeautifulSoup(html, "html.parser")
    cands = []
    for a in soup.find_all("a", href=True):
        href = a["href"]
        txt  = (a.get_text() or "").strip().lower()
        if ("/photos" in href or "/albums" in href or "/media/set" in href or "sk=photos" in href or "v=photos" in href):
            if any(k in txt for k in ("see","more","daha","next","ileri","show","load","tümünü","tümünü gör")):
                cands.append(href)
        if ("v=photos" in href) or ("sk=photos" in href) or ("photos_albums" in href):
            cands.append(href)
    uniq, seen = [], set()
    for l in cands:
        full = l if l.startswith("http") else urljoin(BASE_MBASIC, l)
        if full not in seen:
            uniq.append(full); seen.add(full)
    return uniq

def _extract_image_src(html: str):
    soup = BeautifulSoup(html, "html.parser")
    og = soup.find("meta", attrs={"property":"og:image"})
    if og and og.get("content"):
        src = _safe_image_unwrap(og["content"])
        return src if _likely_photo(src) else None
    img = soup.find("img")
    if img and img.get("src"):
        src = _safe_image_unwrap(img["src"])
        return src if _likely_photo(src) else None
    return None

def _extract_owner_id(html: str):
    pats = [
        r'profile\.php\?id=(\d+)',
        r'entity_id[\'"]\s*:\s*["\'](\d+)["\']',
        r'content_owner_id_new[\'"]\s*:\s*["\'](\d+)["\']',
        r'"owner_id"\s*:\s*"?(\d+)"?',
        r'fb://profile/(\d+)',
        r'"profile_id"\s*:\s*"?(\d+)"?',
        r'data-owner-id="(\d+)"'
    ]
    for p in pats:
        m = re.search(p, html)
        if m: return m.group(1)
    return None

async def get_fb_photos(username: str, limit: int = 12):
    u = username.strip().lstrip("@")
    meta = {"visited": [], "queued": [], "owner_id": None}
    photos = []
    seen_urls = set()

    # ana profilden owner_id dene
    sc0, h0 = await _get(f"{BASE_MBASIC}/{u}", timeout=20)
    if sc0 == 200 and isinstance(h0, str):
        oid = _extract_owner_id(h0)
        if oid: meta["owner_id"] = oid

    seeds = [
        f"{BASE_MBASIC}/{u}/photos/",
        f"{BASE_MBASIC}/{u}/photos_by",
        f"{BASE_MBASIC}/{u}/photos_of",
        f"{BASE_MBASIC}/{u}/photos_albums",
        f"https://m.facebook.com/{u}?v=photos",
        f"https://m.facebook.com/{u}&sk=photos",
    ]
    if meta["owner_id"]:
        oid = meta["owner_id"]
        seeds += [
            f"{BASE_MBASIC}/profile.php?id={oid}&v=photos",
            f"{BASE_MBASIC}/profile.php?id={oid}&sk=photos",
            f"{BASE_MBASIC}/profile.php?id={oid}&sk=photos_albums",
            f"{BASE_MBASIC}/profile.php?id={oid}&v=photos_by",
            f"{BASE_MBASIC}/profile.php?id={oid}&v=photos_of",
        ]

    q = collections.deque()
    visited = set()
    for s in seeds:
        q.append((s,0)); meta["queued"].append(s)

    MAX_DEPTH = 10
    MAX_VISIT = 60

    while q and len(meta["visited"]) < MAX_VISIT and len(photos) < limit:
        url, depth = q.popleft()
        if url in visited: continue
        visited.add(url)
        meta["visited"].append(url)

        sc, html = await _get(url, timeout=20)
        if sc != 200 or not isinstance(html,str): continue

        for p in _extract_imgs_from_html(html, url):
            if len(photos) >= limit: break
            if p["url"] not in seen_urls:
                photos.append(p); seen_urls.add(p["url"])

        if len(photos) >= limit: break

        step = 0
        for link in _find_detail_links(html):
            if len(photos) >= limit or step >= 120: break
            sc2, h2 = await _get(link, timeout=15); step += 1
            if sc2 != 200 or not isinstance(h2,str): continue
            src = _extract_image_src(h2)
            if src and _host_ok(src) and (src not in seen_urls):
                photos.append({"url": src, "page": link, "source": "mbasic"})
                seen_urls.add(src)

        if len(photos) >= limit: break

        if depth < MAX_DEPTH:
            for nxt in _find_pagination_links(html):
                if nxt not in visited:
                    q.append((nxt, depth+1))
                    meta["queued"].append(nxt)

    # Playwright fallback (aynı /photos sayfası)
    if len(photos) < limit and os.getenv("USE_BROWSER_FALLBACK","true").lower() in ("1","true","yes"):
        try:
            from app.services.browser_fetch import fetch_page_html
            list_url = f"{BASE_MBASIC}/{u}/photos/"
            bhtml = await fetch_page_html(list_url, wait_selector="img", timeout_ms=int(os.getenv("TIMEOUT_MS","30000")))
            more = _extract_imgs_from_html(bhtml, list_url)
            meta["browser"] = {"ok": bool(more), "len": len(bhtml), "found": len(more)}
            for p in more:
                if len(photos) >= limit: break
                if p["url"] not in seen_urls:
                    photos.append(p); seen_urls.add(p["url"])
        except Exception as e:
            meta["browser"] = {"ok": False, "error": repr(e)}

    photos = photos[:limit]
    return {"username": u, "photos": photos, "count": len(photos), "meta": meta}
# === PATCH START: stronger browser fallback for Pages ===
async def _browser_fallback_collect(u, limit, seen_urls, photos, meta):
    try:
        from app.services.browser_fetch import fetch_page_html
    except Exception as e:
        meta["browser"] = {"ok": False, "error": repr(e)}
        return

    paths = [
        f"{BASE_MBASIC}/{u}/photos/",
        f"{BASE_MBASIC}/{u}/photos_by",
        f"{BASE_MBASIC}/{u}/photos_albums",
        f"{BASE_MBASIC}/pg/{u}/photos/",
    ]
    found = 0
    for list_url in paths:
        if len(photos) >= limit: break
        try:
            bhtml = await fetch_page_html(list_url, wait_selector="a", timeout_ms=int(os.getenv("TIMEOUT_MS","30000")))
            # 1) sayfadaki img'lerden direkt al
            for p in _extract_imgs_from_html(bhtml, list_url):
                if len(photos) >= limit: break
                if p["url"] not in seen_urls:
                    photos.append(p); seen_urls.add(p["url"]); found += 1

            # 2) sayfadaki "detay" linklerine girip og:image çıkar
            for link in _find_detail_links(bhtml):
                if len(photos) >= limit: break
                sc2, h2 = await _get(link, timeout=15)
                if sc2 != 200 or not isinstance(h2,str): continue
                src = _extract_image_src(h2)
                if src and _host_ok(src) and (src not in seen_urls):
                    photos.append({"url": src, "page": link, "source": "mbasic"}); seen_urls.add(src); found += 1
        except Exception:
            continue
    meta["browser"] = {"ok": found>0, "found": found}

# === PATCH END ===

def _viewer_id_from_cookie():
    try:
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "secrets"))
        path = os.path.join(base, "fb.cookie")
        if not os.path.exists(path): 
            return None
        raw = open(path, "r", encoding="utf-8-sig").read().strip()
        if raw.lower().startswith("cookie:"):
            raw = raw.split(":",1)[1].strip()
        for part in raw.replace("\r"," ").replace("\n"," ").split(";"):
            part = part.strip()
            if not part or "=" not in part: 
                continue
            k,v = part.split("=",1)
            if k.strip()=="c_user" and v.strip().isdigit():
                return v.strip()
    except Exception:
        pass
    return None

# --- patched seeds extend (spacex fix) ---
try:
    if "seeds" in globals() and isinstance(seeds, list):
        _u = username if "username" in globals() else None
        _ext = [
            f"https://mbasic.facebook.com/{_u}/photos" if _u else None,
            f"https://mbasic.facebook.com/{_u}?v=photos" if _u else None,
            f"https://m.facebook.com/{_u}/photos" if _u else None,
            f"https://m.facebook.com/{_u}?sk=photos" if _u else None,
            f"https://m.facebook.com/pg/{_u}/photos" if _u else None,
            f"https://m.facebook.com/{_u}/photos_stream" if _u else None,
            f"https://m.facebook.com/{_u}?sk=photos_stream" if _u else None,
        ]
        for _s in [x for x in _ext if x]:
            if _s not in seeds: seeds.append(_s)
except Exception:
    pass
# --- end patch ---

# --- patched seeds extend (www support) ---
try:
    if "seeds" in globals() and isinstance(seeds, list) and "username" in globals():
        _u = username.strip().lstrip("@")
        _www = f"https://www.facebook.com/{_u}"
        ext = [
            f"{_www}/photos", f"{_www}?sk=photos",
            f"{_www}/photos_by", f"{_www}?sk=photos_by",
            f"{_www}/media", f"{_www}/timeline/photos/",
            f"https://www.facebook.com/pg/{_u}/photos",
            f"https://www.facebook.com/pg/{_u}/photos/?ref=page_internal&type=3",
        ]
        for _s in ext:
            if _s not in seeds: seeds.append(_s)
except Exception:
    pass
# --- end patch ---
