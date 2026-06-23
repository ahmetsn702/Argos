# -*- coding: utf-8 -*-
import sys, os, re, asyncio
from urllib.parse import urlparse
from playwright.async_api import async_playwright

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"

def _cookie_header_for(url: str) -> str:
    """secrets\*.cookie içinden uygun header'ı oku"""
    try:
        host = urlparse(url).netloc.lower()
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "secrets"))
        fname = None
        if "facebook" in host or "fbcdn" in host: fname = "fb.cookie"
        elif "instagram" in host: fname = "ig.cookie"
        elif "twitter" in host or host.endswith("x.com"): fname = "x.cookie"
        if not fname: return ""
        path = os.path.join(base, fname)
        if not os.path.exists(path): return ""
        s = open(path, "r", encoding="utf-8").read().strip()
        if s.lower().startswith("cookie:"): s = s.split(":",1)[1].strip()
        return s
    except Exception:
        return ""

async def fetch_page_html(url: str, wait_selector: str = "", timeout_ms: int = 20000) -> str:
    async with async_playwright() as p:
        extra = {}
        ch = _cookie_header_for(url)
        if ch: extra["extra_http_headers"] = {"Cookie": ch}
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 850}, **extra)
        page = await ctx.new_page()
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        if wait_selector:
            try: await page.wait_for_selector(wait_selector, timeout=timeout_ms)
            except Exception: pass
        html = await page.content()
        await browser.close()
        return html

async def fetch_selector_text(url: str, selector: str, timeout_ms: int = 20000) -> str:
    async with async_playwright() as p:
        extra = {}
        ch = _cookie_header_for(url)
        if ch: extra["extra_http_headers"] = {"Cookie": ch}
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(user_agent=UA, viewport={"width": 1366, "height": 850}, **extra)
        page = await ctx.new_page()
        await page.goto(url, timeout=timeout_ms, wait_until="domcontentloaded")
        await page.wait_for_selector(selector, timeout=timeout_ms)
        txt = await page.locator(selector).inner_text()
        await browser.close()
        return (txt or "").strip()
