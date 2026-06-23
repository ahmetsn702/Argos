# app/services/ig_profile.py
# -*- coding: utf-8 -*-
"""Instagram profile fetching helpers used by /tester endpoints."""
from __future__ import annotations

import os
from typing import Dict, Optional, Tuple

import httpx

from app.utils.ig_helpers import ig_headers


async def fetch_user_info(username: str):
    """Hit IG's `web_profile_info` endpoint.

    Returns (user_id, profile_pic_url_hd_or_url). Either may be None on failure.
    """
    if not username:
        return None, None

    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    try:
        async with httpx.AsyncClient(timeout=25, follow_redirects=True) as client:
            r = await client.get(url, headers=ig_headers())
    except httpx.HTTPError:
        return None, None

    if r.status_code != 200:
        return None, None

    try:
        data = r.json().get("data", {}) or {}
    except ValueError:
        return None, None

    u = data.get("user", {}) or {}
    return (
        u.get("id"),
        u.get("profile_pic_url_hd") or u.get("profile_pic_url"),
    )


async def compare_ig_x_plus(
    user: str,
    prefer_native: int = 0,
    with_bio: int = 1,
) -> Dict:
    """Wrap the existing /tester/compare-ig-x endpoint and enrich with IG bio.

    Mirrors the original behaviour: HTTP self-call to /tester/compare-ig-x then
    attaches `profile.ig` from `ig_profile_by_username`.
    """
    # Lazy import to avoid hard dependency at import time
    from app.tools.ig_native import ig_profile_by_username

    base_url = os.getenv("SELF_BASE_URL", "http://127.0.0.1:8020")

    async with httpx.AsyncClient(timeout=30.0) as client:
        r = await client.post(
            f"{base_url}/tester/compare-ig-x",
            data={"user": user, "prefer_native": prefer_native},
        )
        base = r.json()

    base["profile"] = {"ig": ig_profile_by_username(user) if with_bio else None}
    return base


__all__ = ["fetch_user_info", "compare_ig_x_plus"]
