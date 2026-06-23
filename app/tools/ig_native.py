import os, requests, json
from urllib.parse import unquote

ROOT = os.path.abspath(os.getcwd())
COOKIE_FILE = os.path.join(ROOT, "app", "secrets", "ig.cookie")

def _cookie_header_from_file(path=COOKIE_FILE):
    raw = open(path, "rb").read().decode("utf-8","ignore").strip()
    parts = []
    for tok in raw.split(";"):
        tok = tok.strip()
        if "=" in tok:
            k,v = tok.split("=",1)
            parts.append(f"{k.strip()}={unquote(v.strip())}")
    return ";".join(parts)

def ig_profile_by_username(username: str):
    if not username:
        return None
    ck = _cookie_header_from_file()
    UA = os.getenv("IG_USER_AGENT") or "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/141.0.0.0 Safari/537.36"
    hdr = {
        "User-Agent": UA,
        "X-IG-App-ID": "936619743392459",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "Referer": "https://www.instagram.com/",
        "Cookie": ck,
    }
    url = f"https://www.instagram.com/api/v1/users/web_profile_info/?username={username}"
    r = requests.get(url, headers=hdr, timeout=20)
    if r.status_code != 200:
        return {"ok": False, "status": r.status_code}
    j = r.json()
    u = j.get("data",{}).get("user",{}) or {}
    return {
        "ok": True,
        "username": u.get("username"),
        "full_name": u.get("full_name"),
        "biography": u.get("biography"),
        "followers": (u.get("edge_followed_by") or {}).get("count"),
        "following": (u.get("edge_follow") or {}).get("count"),
        "profile_pic_url": u.get("profile_pic_url_hd") or u.get("profile_pic_url"),
        "is_private": u.get("is_private"),
        "is_verified": u.get("is_verified"),
    }