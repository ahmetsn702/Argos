# -*- coding: utf-8 -*-
import os, requests
from bs4 import BeautifulSoup
from urllib.parse import urljoin

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,tr;q=0.8"}

def _get(url, timeout=12):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR:{e!r}"

def _imgs_from_html(html, base, source):
    soup = BeautifulSoup(html, "html.parser")
    urls, seen, out = [], set(), []
    for img in soup.find_all("img", src=True):
        src = img["src"]
        if ("pbs.twimg.com/media" in src) or ("/pic/" in src) or ("twimg.com/profile_images" in src):
            full = src if src.startswith("http") else urljoin(base, src)
            urls.append(full)
    for u in urls:
        if u not in seen:
            out.append({"url": u, "page": base, "source": source})
            seen.add(u)
    return out

async def get_x_photos(username: str, limit: int = 12):
    u = username.strip().lstrip("@")
    meta, photos = {}, []

    base_m = f"https://mobile.twitter.com/{u}"
    sc, html = _get(base_m, timeout=12)
    meta["mobile"] = {"status": sc, "len": (len(html) if isinstance(html, str) else 0)}
    if sc == 200 and isinstance(html, str):
        photos += _imgs_from_html(html, base_m, "x-mobile")

    for host in ["https://nitter.net", "https://nitter.poast.org"]:
        if len(photos) >= limit: break
        url = f"{host}/{u}/media"
        sc2, html2 = _get(url, timeout=12)
        meta[f"nitter_{host.split('//')[1]}"] = {"status": sc2, "len": (len(html2) if isinstance(html2, str) else 0)}
        if sc2 == 200 and isinstance(html2, str):
            photos += _imgs_from_html(html2, url, "nitter")

    if (not photos) and os.getenv("USE_BROWSER_FALLBACK","true").lower() in ("1","true","yes"):
        try:
            from app.services.browser_fetch import fetch_page_html
            html = await fetch_page_html(base_m, wait_selector="title", timeout_ms=int(os.getenv("TIMEOUT_MS","20000")))
            more = _imgs_from_html(html, base_m, "x-browser")
            photos = photos or more
            meta["browser"] = {"ok": bool(more), "len": len(html)}
        except Exception as e:
            meta["browser"] = {"ok": False, "error": repr(e)}

    # basit filtre + kırp
    uniq, seen = [], set()
    for p in photos:
        uurl = p["url"]
        if uurl in seen: continue
        if any(k in uurl for k in ("pbs.twimg.com", "/pic/")):
            uniq.append(p); seen.add(uurl)
    if not uniq: uniq = photos
    uniq = uniq[:limit]
    return {"username": u, "photos": uniq, "count": len(uniq), "meta": meta}
