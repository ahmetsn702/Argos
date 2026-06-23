import asyncio
from app.utils import lk_title_guard

async def _safe_page_title(page, *, tries: int = 3, wait_ms: int = 10000):
    """
    LinkedIn gibi agresif redirect yapan sayfalarda
    'Execution context was destroyed' hatasına karşı dayanıklı title okuma.
    """
    last_err = None
    for _ in range(tries):
        try:
            await page.wait_for_load_state("domcontentloaded", timeout=wait_ms)
            # [DEMO] Use safe page title to avoid 'Execution context was destroyed'
            return await lk_title_guard.safe_title(page)
        except Exception as e:
            msg = str(e)
            if "Execution context was destroyed" in msg or "Execution context was destroyed" in repr(e):
                last_err = e
                await asyncio.sleep(0.4)
                continue
            raise
    # son çare: içerikten og:title dene
    try:
        html = await page.content()
        import re as _re
        m = _re.search(r'<meta[^>]+property=["' + "'" + r']og:title["' + "'" + r'][^>]+content=["' + "'" + r']([^"<]+)', html, _re.I)
        if m:
            return m.group(1)
    except Exception:
        pass
    if last_err:
        raise last_err
    return ""
import json, time, requests
from typing import Optional, Dict
from urllib.parse import urlsplit, urlunsplit, parse_qsl
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError  # type: ignore
from app.core.config import (HEADLESS_MODE, USE_SYSTEM_CHROME, LINKEDIN_CACHE_TTL, REQUEST_TIMEOUT, LI_AT)
from app.utils.common import ua, clean_text
_linkedin_cache: Dict[str, Dict] = {}
def normalize_linkedin_url(url: str) -> str:
    try:
        parts = urlsplit(url.strip()); scheme = "https"; netloc = "www.linkedin.com"; path = parts.path or ""
        if not path.endswith("/"): path = path + "/"
        qs = [(k,v) for (k,v) in parse_qsl(parts.query or "") if not k.lower().startswith("utm_")]
        return urlunsplit((scheme, netloc, path, "&".join(f"{k}={v}" for k,v in qs), ""))
    except Exception: return url
def _launch_browser(p):
    if USE_SYSTEM_CHROME:
        for ch in ("chrome","msedge"):
            try: return p.chromium.launch(channel=ch, headless=HEADLESS_MODE)
            except Exception: continue
    return p.chromium.launch(headless=HEADLESS_MODE)
def linkedin_public_fetch(url: str) -> Dict:
    try:
        s = requests.Session(); s.headers.update(ua()); r = s.get(url, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        soup = BeautifulSoup(r.text or "", "html.parser")
        name = ""; headline = ""
        og_title = soup.find("meta", property="og:title"); 
        if og_title and og_title.has_attr("content"): name = clean_text(og_title["content"])
        og_desc  = soup.find("meta", property="og:description")
        if og_desc and og_desc.has_attr("content"): headline = clean_text(og_desc["content"])
        return {"url": url, "profile_name": name, "headline": headline, "about":"", "source":"public_fallback", "note":"LI_AT olmadan sınırlı."}
    except Exception:
        return {"url": url, "profile_name":"", "headline":"", "about":"", "source":"public_fallback", "note":"Public çekim başarısız."}
def scrape_linkedin_cookie(url: str, li_at_cookie: Optional[str] = None) -> Dict:
    cookie = (li_at_cookie or LI_AT or "").strip()
    if not cookie: return linkedin_public_fetch(url)
    with sync_playwright() as p:
        browser = _launch_browser(p)
        context = browser.new_context(user_agent=ua()["User-Agent"], locale="en-US", extra_http_headers={"Accept-Language":"en-US,en;q=0.8"})
        context.add_cookies([
            {"name":"li_at","value":cookie,"domain":".linkedin.com","path":"/"},
            {"name":"lang","value":"v=2&lang=en-us","domain":".linkedin.com","path":"/"},
        ])
        page = context.new_page()
        try:
            # [DEMO] Enforce wait_until for stable navigation
            page.goto("https://www.linkedin.com/feed/", wait_until="domcontentloaded", timeout=25000)
            page.wait_for_timeout(800)
            # [DEMO] Enforce wait_until for stable navigation
            page.goto(url, wait_until="domcontentloaded", timeout=30000)
            try: page.wait_for_selector("h1", timeout=12000)
            except Exception: pass
            profile_name=headline=about_text=""
            try: profile_name = clean_text(page.locator("h1").first.inner_text(timeout=5000))
            except Exception: pass
            try: headline = clean_text(page.locator("div.text-body-medium.break-words").first.inner_text(timeout=5000))
            except Exception: pass
            try:
                about = page.locator("section.pvs-profile-section:has(h2:has-text('About')) div.inline-show-more-text").first
                if about and about.is_visible(): about_text = clean_text(about.inner_text())
            except Exception: pass
            return {"url": url, "profile_name": profile_name, "headline": headline, "about": about_text, "source":"playwright_cookie"}
        except PlaywrightTimeoutError as e:
            return {"url": url, "profile_name":"", "headline":"", "about":"", "source":"public_fallback", "note":"Cookie ile çekim zaman aşımı.", "fallback_reason": str(e)}
        except Exception as e:
            try: page.screenshot(path="linkedin_error.png", full_page=True)
            except Exception: pass
            return {"url": url, "profile_name":"", "headline":"", "about":"", "source":"public_fallback", "note":"Cookie ile çekim başarısız.", "fallback_reason": str(e)}
        finally:
            browser.close()
def linkedin_cached_fetch(clean_url: str, force_public: bool=False, li_at: Optional[str]=None) -> Dict:
    now = time.time(); hit = _linkedin_cache.get(clean_url)
    if hit and (now - hit.get("_ts",0) <= LINKEDIN_CACHE_TTL):
        out = dict(hit); out["cache"]=True; return out
    data = linkedin_public_fetch(clean_url) if force_public else scrape_linkedin_cookie(clean_url, li_at_cookie=li_at)
    data["_ts"]=now; _linkedin_cache[clean_url]=data.copy(); return data