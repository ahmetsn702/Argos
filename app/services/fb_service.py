# -*- coding: utf-8 -*-
import os, re, json, time
import httpx
from urllib.parse import urljoin
from bs4 import BeautifulSoup

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
HEADERS = {"User-Agent": UA, "Accept-Language": "en-US,en;q=0.9,tr;q=0.8"}

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

def _abs(base, href):
    if not href: return None
    return href if href.startswith("http") else urljoin(base, href)

def _parse_profile(html):
    soup = BeautifulSoup(html, "html.parser")
    title = (soup.title.get_text(strip=True) if soup.title else "") or \
            (soup.find("meta", attrs={"property":"og:title"}) or {}).get("content","")
    bio = (soup.find("meta", attrs={"name":"description"}) or {}).get("content","") or \
          (soup.find("meta", attrs={"property":"og:description"}) or {}).get("content","")
    og_img = (soup.find("meta", attrs={"property":"og:image"}) or {}).get("content","")
    if title.lower().startswith("facebook"): title = ""
    return title.strip(), (bio or "").strip(), og_img

async def _get(url, timeout=15):
    try:
        h = dict(HEADERS)
        ch = _cookie_header()
        if ch: h["Cookie"] = ch
        async with httpx.AsyncClient(timeout=timeout) as client:
            r = await client.get(url, headers=h, follow_redirects=True)
        return r.status_code, r.text
    except Exception as e:
        return 0, f"ERR:{e!r}"

async def get_fb_profile(username: str):
    u = username.strip().lstrip("@")
    sources = [
        ("mbasic", f"https://mbasic.facebook.com/{u}"),
        ("mobile", f"https://m.facebook.com/{u}"),
        ("www",    f"https://www.facebook.com/{u}"),
    ]
    meta = {}
    display_name = ""
    bio = ""
    pic = ""
    status = "unknown"

    for name, url in sources:
        sc, html = await _get(url)
        ok = isinstance(html, str) and sc==200 and ("<html" in html.lower())
        meta[name] = {"status": sc, "len": (len(html) if isinstance(html,str) else 0), "ok": bool(ok)}
        if not ok: continue
        t,b,p = _parse_profile(html)
        display_name = display_name or t
        bio = bio or b
        pic = pic or p
        if display_name or bio or pic:
            status = "exists"
            break

    if status!="exists":
        try:
            from app.services.browser_fetch import fetch_page_html
            html = await fetch_page_html(f"https://m.facebook.com/{u}", wait_selector="title", timeout_ms=int(os.getenv("TIMEOUT_MS","20000")))
            t,b,p = _parse_profile(html)
            display_name = display_name or t
            bio = bio or b
            pic = pic or p
            meta["browser"] = {"ok": bool(display_name or bio or pic), "len": len(html)}
            if display_name or bio or pic:
                status = "exists"
        except Exception as e:
            meta["browser"] = {"ok": False, "error": repr(e)}

    return {
        "status": status,
        "username": u,
        "display_name": display_name,
        "bio": bio,
        "profile_pic": pic,
        "profile_url": f"https://facebook.com/{u}",
        "meta": meta,
    }
