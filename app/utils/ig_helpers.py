# app/utils/ig_helpers.py
# -*- coding: utf-8 -*-
"""Shared helpers for Instagram tester endpoints.

Centralises:
- UA_IG: user-agent string (env override)
- cookie + header builders for IG private API
- HTML unescape
- proxy host allow-lists
"""
from __future__ import annotations

import html
import os
import re
from typing import Dict


# --- User agent ---------------------------------------------------------------
UA_IG = os.getenv(
    "IG_USER_AGENT",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36",
)

# --- Proxy allow-lists --------------------------------------------------------
# Used by /tester/ig-proxy (regex match)
IG_PROXY_HOST_PATTERNS = (
    r".*\.fbcdn\.net$",
    r".*\.cdninstagram\.com$",
    r"instagram\.[\w-]+\.fna\.fbcdn\.net$",
)

# Used by /tester/pp-proxy (suffix match)
PP_PROXY_HOST_SUFFIXES = ("fbcdn.net", "cdninstagram.com")


def ok_proxy_host(host: str) -> bool:
    """Return True if `host` matches any /ig-proxy allowed pattern."""
    h = host or ""
    return any(re.match(p, h) for p in IG_PROXY_HOST_PATTERNS)


def ok_pp_proxy_host(host: str) -> bool:
    """Return True if `host` ends with any /pp-proxy allowed suffix."""
    h = (host or "").lower()
    return any(h.endswith(sfx) for sfx in PP_PROXY_HOST_SUFFIXES)


# --- IG cookie + headers ------------------------------------------------------
def ig_cookie() -> str:
    """Return IG session cookie from app/secrets/ig.cookie (best-effort)."""
    p = os.path.join(os.getcwd(), "app", "secrets", "ig.cookie")
    if not os.path.exists(p):
        return ""
    try:
        with open(p, "r", encoding="utf-8", errors="ignore") as fh:
            return fh.read().strip()
    except OSError:
        return ""


def ig_headers() -> Dict[str, str]:
    """Headers for IG private/web API calls. Adds Cookie + CSRF if available."""
    h: Dict[str, str] = {
        "User-Agent": UA_IG,
        "Accept": "application/json",
        "X-IG-App-ID": "936619743392459",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.instagram.com/",
    }
    ck = ig_cookie()
    if ck:
        h["Cookie"] = ck
        m = re.search(r"csrftoken=([^;]+)", ck)
        if m:
            h["X-CSRFToken"] = m.group(1)
    return h


def ig_image_headers() -> Dict[str, str]:
    """Headers for fetching IG CDN image bytes (proxy use)."""
    return {
        "User-Agent": UA_IG,
        "Referer": "https://www.instagram.com/",
        "Accept": "image/avif,image/webp,image/*,*/*;q=0.8",
    }


# --- Image proxy fetch --------------------------------------------------------
async def fetch_proxy_image(
    raw_url: str,
    *,
    host_check,
    timeout: int = 25,
    cache_control: str = "no-store",
):
    """Fetch an image through an allow-listed host. Returns a `Response`-shaped
    dict with keys: status_code, content, media_type, headers, error.

    Router code wraps the result in fastapi.Response. We avoid importing
    fastapi here to keep the helper pure-Python.
    """
    import urllib.parse as _up
    import httpx as _httpx

    raw = _up.unquote(raw_url or "")
    pu = _up.urlparse(raw)
    if pu.scheme not in ("http", "https"):
        return {"status_code": 400, "content": b"bad-scheme", "media_type": None, "headers": {}}
    if not host_check(pu.hostname or ""):
        return {"status_code": 403, "content": b"forbidden-host", "media_type": None, "headers": {}}
    try:
        async with _httpx.AsyncClient(timeout=timeout, follow_redirects=True) as cli:
            r = await cli.get(raw, headers=ig_image_headers())
    except _httpx.HTTPError as e:
        return {"status_code": 502, "content": f"proxy-error:{e}".encode("utf-8"),
                "media_type": None, "headers": {}}
    if r.status_code != 200:
        return {"status_code": 502, "content": b"", "media_type": None,
                "headers": {"X-Err": f"cdn-{r.status_code}"}}
    return {
        "status_code": 200,
        "content": r.content,
        "media_type": r.headers.get("content-type", "image/jpeg"),
        "headers": {"Cache-Control": cache_control},
    }


# --- IG URL unescape ----------------------------------------------------------
def unescape_ig_url(u: str) -> str:
    """Undo IG's `\\/` and `\\u0026` escapes; resolve HTML entities."""
    if not u:
        return u
    u = u.replace("\\/", "/").replace("\\u0026", "&")
    return html.unescape(u)


__all__ = [
    "UA_IG",
    "IG_PROXY_HOST_PATTERNS",
    "PP_PROXY_HOST_SUFFIXES",
    "ok_proxy_host",
    "ok_pp_proxy_host",
    "ig_cookie",
    "ig_headers",
    "ig_image_headers",
    "fetch_proxy_image",
    "unescape_ig_url",
]
