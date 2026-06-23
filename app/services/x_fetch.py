# -*- coding: utf-8 -*-
import re, requests, json
from typing import Dict, Optional

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
NITTERS = ["nitter.net","nitter.poast.org","nitter.privacydev.net","nitter.fdn.fr"]

def _clean(u: Optional[str]) -> str:
    return (u or "").strip().lstrip("@")

def _strip_html(s: str) -> str:
    s = re.sub(r"<[^>]+>", " ", s or "")
    return re.sub(r"\s+", " ", s).strip()

def _get(url: str, accept: Optional[str]=None, timeout: int=8):
    h = {"User-Agent": UA}
    if accept: h["Accept"] = accept
    return requests.get(url, headers=h, timeout=timeout)

def _try_widget(u: str, meta: dict, name: str):
    tried = [
        f"https://cdn.syndication.twimg.com/widgets/followbutton/info.json?screen_names={u}",
        f"https://r.jina.ai/https://cdn.syndication.twimg.com/widgets/followbutton/info.json?screen_names={u}",
        f"https://syndication.twitter.com/widgets/followbutton/info.json?screen_names={u}",
        f"https://r.jina.ai/https://syndication.twitter.com/widgets/followbutton/info.json?screen_names={u}",
    ]
    for url in tried:
        try:
            r = _get(url, accept="application/json")
            txt = r.text or ""
            item = {"status": getattr(r,"status_code",None), "len": len(txt), "ok": False}
            j = None
            try:
                j = r.json() if "r.jina.ai" not in url else json.loads(txt)
            except Exception as je:
                item["error"] = repr(je)
            if isinstance(j, list) and j:
                e = j[0] or {}
                nm = (e.get("name") or "").strip()
                un = (e.get("screen_name") or "").strip()
                if nm: name = nm
                if un: u = un
                item["ok"] = True
                meta["widget"] = item
                return u, name
            meta["widget"] = item
        except Exception as e:
            meta["widget"] = {"status": None, "len": 0, "error": repr(e)}
    return u, name

async def fetch_x_profile_simple(username: str) -> Dict:
    u = _clean(username)
    if not u:
        return {"status":"unknown","username":"","display_name":"","bio":"","profile_url":""}

    name, bio, status = "", "", "unknown"
    meta = {"widget":{}, "mobile":{}, "nitter":[], "title":{}, "browser":{}}

    # 1) widget
    u, name = _try_widget(u, meta, name)
    if name: status = "exists"

    # 2) mobile.twitter.com (OG + UserDescription + <title>)
    if not name or not bio:
        try:
            r = _get(f"https://r.jina.ai/https://mobile.twitter.com/{u}")
            html = r.text or ""
            mt  = re.search(r'<meta[^>]+property="og:title"[^>]+content="([^"]+)"', html, re.I)
            md  = re.search(r'<meta[^>]+(name="description"|property="og:description")[^>]+content="([^"]+)"', html, re.I)
            md2 = re.search(r'data-testid="UserDescription"[^>]*>(.*?)</div>', html, re.S|re.I)
            tit = re.search(r"<title>(.*?)</title>", html, re.S|re.I)
            if mt and not name:
                raw = mt.group(1); name = re.sub(r"\s*\(@.*?\).*", "", raw).strip()
            if not name and tit:
                raw = _strip_html(tit.group(1)); name = re.sub(r"\s*\(@.*?\).*", "", raw).strip()
            if not bio:
                if md2: bio = _strip_html(md2.group(1))
                elif md: bio = _strip_html(md.group(2))
            if name: status = "exists"
            meta["mobile"] = {"status": getattr(r,"status_code",None), "len": len(html), "found_title": bool(mt or tit), "found_desc": bool(md or md2)}
        except Exception as e:
            meta["mobile"] = {"status": None, "len": 0, "error": repr(e)}

    # 3) Çoklu Nitter
    if not bio:
        for host in NITTERS:
            itm = {"host": host, "status": None, "len": 0, "found_bio": False}
            try:
                r = _get(f"https://r.jina.ai/https://{host}/{u}")
                html = r.text or ""
                m = re.search(r'class="profile-bio"[^>]*>(.*?)</div>', html, re.S|re.I) or \
                    re.search(r'class="bio"[^>]*>(.*?)</div>', html, re.S|re.I)
                if m:
                    bio = _strip_html(m.group(1))
                    itm["found_bio"] = True
                itm["status"] = getattr(r,"status_code",None); itm["len"] = len(html)
            except Exception as e:
                itm["error"] = repr(e)
            meta["nitter"].append(itm)
            if bio: break

    # 4) x.com title fallback
    if not name:
        try:
            r = _get(f"https://r.jina.ai/https://x.com/{u}")
            html = r.text or ""
            tit = re.search(r"<title>(.*?)</title>", html, re.S|re.I)
            if tit:
                raw = _strip_html(tit.group(1))
                name = re.sub(r"\s*\(@.*?\).*", "", raw).strip()
                if name: status = "exists"
            meta["title"] = {"status": getattr(r,"status_code",None), "len": len(html), "found": bool(tit)}
        except Exception as e:
            meta["title"] = {"status": None, "len": 0, "error": repr(e)}

    # 5) Browser fallback (Playwright) — DOM'dan bio çek
    if (not name) or (not bio):
        try:
            from app.services.browser_fetch import fetch_page_html, fetch_selector_text
            urlm = f"https://mobile.twitter.com/{u}"
            html = await fetch_page_html(urlm, wait_selector='[data-testid="UserName"]', timeout_ms=15000)
            tit = re.search(r"<title>(.*?)</title>", html, re.S|re.I)
            if (not name) and tit:
                raw = _strip_html(tit.group(1))
                name = re.sub(r"\s*\(@.*?\).*", "", raw).strip()
            if not bio:
                try:
                    t = await fetch_selector_text(urlm, '[data-testid="UserDescription"]', timeout_ms=15000)
                    if t:
                        bio = _strip_html(t)
                except Exception as te:
                    meta["browser_text_error"] = repr(te)
            meta["browser"] = {"ok": bool(name or bio), "len": len(html)}
            if name or bio:
                status = "exists"
        except Exception as e:
            meta["browser"] = {"ok": False, "error": repr(e)}

    return {
        "status": status,
        "username": u,
        "display_name": name,
        "bio": bio,
        "profile_url": f"https://x.com/{u}",
        "meta": meta
    }

async def fetch_x_profile_vfast(username: str) -> Dict:
    return await fetch_x_profile_simple(username)


class XService:
    """Backward-compat wrapper around x_fetch functions."""

    async def fetch_bio(self, username, session=None):
        return await fetch_x_profile_simple(username)

    async def profile(self, username):
        return await fetch_x_profile_simple(username)

    async def fast_profile(self, username):
        return await fetch_x_profile_vfast(username)

    @staticmethod
    async def fetch_profile(username: str):
        return await fetch_x_profile_simple(username)

    @staticmethod
    async def fetch_fast(username: str):
        return await fetch_x_profile_vfast(username)
