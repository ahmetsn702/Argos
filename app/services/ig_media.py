# app/services/ig_media.py
# -*- coding: utf-8 -*-
"""Instagram media list / scrape / ZIP helpers used by /tester endpoints."""
import io
import json
import re
import zipfile
from typing import Dict, List, Optional

import httpx

from app.utils.ig_helpers import (
    UA_IG,
    ig_headers,
    unescape_ig_url,
)
from app.services.ig_profile import fetch_user_info


async def fetch_media_html(username: str, limit: int = 12) -> Dict:
    """Pull recent post images from the public profile HTML (no login)."""
    if not username:
        return {"ok": False, "error": "user required"}

    limit = max(1, min(int(limit or 12), 24))
    url = f"https://www.instagram.com/{username}/"
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            r = await client.get(url, headers={"User-Agent": UA_IG, "Accept": "text/html,application/xhtml+xml"})
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e)}

    if r.status_code != 200:
        return {"ok": False, "status": r.status_code, "error": r.text[:200]}

    t = r.text
    scodes = re.findall(r'"shortcode"\s*:\s*"([A-Za-z0-9_-]{5,})"', t)
    urls = re.findall(r'"display_url"\s*:\s*"(https:\\/\\/[^"]+)"', t)
    thumbs = re.findall(r'"thumbnail_src"\s*:\s*"(https:\\/\\/[^"]+)"', t)

    items: List[Dict] = []
    seen = set()
    for i, sc in enumerate(scodes):
        if sc in seen:
            continue
        seen.add(sc)
        im = unescape_ig_url(urls[i]) if i < len(urls) else None
        th = unescape_ig_url(thumbs[i]) if i < len(thumbs) else im
        items.append({"shortcode": sc, "image": im, "thumb": th, "link": f"https://www.instagram.com/p/{sc}/"})
        if len(items) >= limit:
            break

    return {"ok": True, "items": items}


def _media_node_to_item(node: Dict) -> Dict:
    sc = node.get("shortcode")
    cap = (((node.get("edge_media_to_caption") or {}).get("edges") or [{}])[0] or {}).get("node", {}).get("text", "")
    return {
        "shortcode": sc,
        "is_video": node.get("is_video", False),
        "image": node.get("display_url") or node.get("thumbnail_src"),
        "thumb": node.get("thumbnail_src") or node.get("display_url"),
        "caption": cap,
        "link": f"https://www.instagram.com/p/{sc}/" if sc else None,
    }


async def fetch_recent_media(username: str, limit: int = 9) -> Dict:
    """Cookie-authenticated recent media for public accounts (best-effort)."""
    limit = max(1, min(int(limit or 9), 24))
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            r = await client.get(url, headers=ig_headers())
            if r.status_code != 200:
                return {"ok": False, "status": r.status_code, "error": r.text[:200]}

            try:
                u = (r.json().get("data") or {}).get("user") or {}
            except ValueError:
                return {"ok": False, "error": "invalid json"}

            is_private = u.get("is_private", False)
            edges = ((u.get("edge_owner_to_timeline_media") or {}).get("edges")) or []
            items = [_media_node_to_item((e or {}).get("node") or {}) for e in edges[:limit]]

            if not items and u.get("id") and not is_private:
                try:
                    r2 = await client.get(
                        "https://www.instagram.com/graphql/query/",
                        params={
                            "query_hash": "58b6785bea111c67129decbe6a448951",
                            "variables": json.dumps({"id": u.get("id"), "first": limit}),
                        },
                        headers=ig_headers(),
                    )
                    if r2.status_code == 200:
                        d = r2.json()
                        nodes = (((d.get("data") or {}).get("user") or {}).get("edge_owner_to_timeline_media") or {}).get("edges") or []
                        items = [_media_node_to_item((e or {}).get("node") or {}) for e in nodes[:limit]]
                except (httpx.HTTPError, ValueError):
                    pass

        return {"ok": True, "is_private": is_private, "items": items}
    except httpx.HTTPError as e:
        return {"ok": False, "error": str(e)}


def _best_image_from_item(it: Dict) -> Optional[str]:
    iv2 = it.get("image_versions2")
    if iv2 and iv2.get("candidates"):
        cand = sorted(iv2["candidates"], key=lambda x: x.get("width", 0), reverse=True)
        return (cand[0] or {}).get("url")
    if it.get("carousel_media"):
        for m in it["carousel_media"]:
            iv = m.get("image_versions2") or {}
            cand = iv.get("candidates") or []
            if cand:
                cand = sorted(cand, key=lambda x: x.get("width", 0), reverse=True)
                return (cand[0] or {}).get("url")
    return None


async def build_media_zip(username: str, limit: int = 12) -> Optional[bytes]:
    """Download recent images for `username` and pack them into a ZIP."""
    username = (username or "").strip().lstrip("@")
    limit = max(1, min(int(limit or 12), 30))

    uid, ppu = await fetch_user_info(username)
    if not uid and not ppu:
        return None

    urls: List[str] = []
    if uid:
        feed_url = f"https://www.instagram.com/api/v1/feed/user/{uid}/?count={max(12, limit * 2)}"
        try:
            async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
                r = await client.get(feed_url, headers=ig_headers())
            if r.status_code == 200:
                items = r.json().get("items") or []
                for it in items:
                    u = _best_image_from_item(it)
                    if u and u not in urls:
                        urls.append(u)
                    if len(urls) >= limit:
                        break
        except (httpx.HTTPError, ValueError):
            pass

    if not urls and ppu:
        urls = [ppu]
    if not urls:
        return None

    buf = io.BytesIO()
    image_headers = {"User-Agent": UA_IG, "Referer": "https://www.instagram.com/"}
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as z:
        async with httpx.AsyncClient(headers=image_headers, timeout=25) as client:
            for i, u in enumerate(urls[:limit]):
                try:
                    rr = await client.get(u)
                    ext = (u.split("?")[0].rsplit(".", 1)[-1] or "jpg").lower()
                    if ext not in ("jpg", "jpeg", "png", "webp"):
                        ext = "jpg"
                    z.writestr(f"{i:02d}.{ext}", rr.content)
                except httpx.HTTPError:
                    continue
        z.writestr(
            "README.txt",
            f"Generated by Footprint ZIP v5\nusername: {username}\ncount: {len(urls[:limit])}\n".encode("utf-8"),
        )
    return buf.getvalue()


__all__ = ["fetch_media_html", "fetch_recent_media", "build_media_zip"]
