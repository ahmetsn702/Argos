# -*- coding: utf-8 -*-
import os, requests
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,tr;q=0.8"}

def _get(url, timeout=12):
    try:
        r = requests.get(url, headers=HEADERS, timeout=timeout, allow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR:{e!r}"

def _extract_img_urls(html, base_url):
    soup = BeautifulSoup(html, "html.parser")
    urls = []

    og = soup.find("meta", attrs={"property": "og:image"})
    if og and og.get("content"):
        urls.append(og["content"])

    for img in soup.find_all("img", src=True):
        src = img["src"]
        if any(s in src for s in ("cdninstagram", "instagram.f", "fbcdn")):
            urls.append(src)

    seen, out = set(), []
    for u in urls:
        if u not in seen:
            out.append({"url": u, "page": base_url, "source": "instagram"})
            seen.add(u)
    return out

async def get_ig_photos(username: str, limit: int = 12):
    u = username.strip().lstrip("@")
    base = f"https://www.instagram.com/{u}/"
    meta, photos = {}, []

    sc, html = _get(base, timeout=12)
    meta["www"] = {"status": sc, "len": (len(html) if isinstance(html, str) else 0)}
    if sc == 200 and isinstance(html, str):
        photos = _extract_img_urls(html, base)

    if (not photos) and os.getenv("USE_BROWSER_FALLBACK","true").lower() in ("1","true","yes"):
        try:
            from app.services.browser_fetch import fetch_page_html
            html = await fetch_page_html(base, wait_selector="header", timeout_ms=int(os.getenv("TIMEOUT_MS","20000")))
            more = _extract_img_urls(html, base)
            photos = photos or more
            meta["browser"] = {"ok": bool(more), "len": len(html)}
        except Exception as e:
            meta["browser"] = {"ok": False, "error": repr(e)}

    photos = photos[:limit]
    return {"username": u, "photos": photos, "count": len(photos), "meta": meta}
