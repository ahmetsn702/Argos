import httpx
from bs4 import BeautifulSoup
from fastapi import APIRouter, Query, HTTPException
from app.utils.common import clean_text
from app.utils import lk_title_guard

router = APIRouter(tags=["linkedin"])

def _normalize_linkedin_url(url: str) -> str:
    url = url.strip()
    if not url: return url
    if "linkedin.com/in/" not in url:
        raise HTTPException(status_code=400, detail="Profil URL'si /in/ içermeli.")
    if not url.startswith("https://"): url = "https://" + url.lstrip("/")
    if "www.linkedin.com" not in url: url = url.replace("linkedin.com","www.linkedin.com")
    if not url.endswith("/"): url += "/"
    return url

@router.get("/linkedin-bio")
async def linkedin_bio(url: str = Query(...)):
    clean = _normalize_linkedin_url(url)
    try:
        async with httpx.AsyncClient(timeout=20, follow_redirects=True) as client:
            r = await client.get(clean)
        s = BeautifulSoup(r.text or "", "html.parser")
        name = ""; headline = ""
        og_title = s.find("meta", property="og:title")
        og_desc  = s.find("meta", property="og:description")
        if og_title and og_title.has_attr("content"): name = clean_text(og_title["content"])
        if og_desc  and og_desc.has_attr("content"):  headline = clean_text(og_desc["content"])
        return {"url": clean, "profile_name": name, "headline": headline, "about": "", "source": "public_fallback"}
    except Exception:
        return {"url": clean, "profile_name": "", "headline": "", "about": "", "source": "public_fallback", "note":"çekim başarısız"}
