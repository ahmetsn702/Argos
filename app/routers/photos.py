# -*- coding: utf-8 -*-
import io, os, re, mimetypes, zipfile, requests
from urllib.parse import urlparse
from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse
from app.services.photos_aggregate import collect_photos

UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
router = APIRouter()

def _safe(s: str) -> str:
    return re.sub(r"[^A-Za-z0-9._-]+", "_", s)[:120] or "file"

def _cookie_for(url: str) -> str:
    try:
        host = urlparse(url).netloc.lower()
        base = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "secrets"))
        fname = None
        if "facebook" in host or "fbcdn" in host: fname = "fb.cookie"
        if not fname: return ""
        path = os.path.join(base, fname)
        if not os.path.exists(path): return ""
        s = open(path, "r", encoding="utf-8").read().strip()
        if s.lower().startswith("cookie:"): s = s.split(":",1)[1].strip()
        return s
    except Exception:
        return ""

@router.get("/photos")
async def photos(username: str, sources: str = "ig,x,fb", limit: int = 12):
    limit = max(1, min(50, limit))
    return await collect_photos(username, sources=sources, limit=limit)

@router.get("/photos/zip")
async def photos_zip(username: str, sources: str = "ig,x,fb", limit: int = 12):
    data = await collect_photos(username, sources=sources, limit=limit)
    buf = io.BytesIO()
    zf = zipfile.ZipFile(buf, "w", compression=zipfile.ZIP_DEFLATED)

    ses = requests.Session()
    ses.headers.update({"User-Agent": UA, "Referer": "https://m.facebook.com/"})

    idx = 1
    for p in data["photos"]:
        url = p["url"]
        try:
            hdr = {}
            ch = _cookie_for(url)
            if ch: hdr["Cookie"] = ch
            r = ses.get(url, timeout=20, stream=True, headers=hdr)
            ct = r.headers.get("Content-Type","")
            ok_ct = ("image/" in ct) or any(url.lower().endswith(ext) for ext in (".jpg",".jpeg",".png",".webp",".gif"))
            if r.status_code == 200 and ok_ct:
                ext = mimetypes.guess_extension((ct.split(";")[0] if ct else "").strip()) or os.path.splitext(url)[1] or ".jpg"
                name = f"{_safe(username)}_{idx:02d}{ext}"
                zf.writestr(name, r.content)
                idx += 1
        except Exception:
            continue

    zf.close()
    buf.seek(0)
    fname = f"photos_{_safe(username)}.zip"
    return StreamingResponse(buf, media_type="application/zip",
                             headers={"Content-Disposition": f'attachment; filename="{fname}"'})

