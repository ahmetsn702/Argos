from fastapi import APIRouter, Query
from typing import Optional
from playwright.sync_api import sync_playwright
from app.utils import lk_title_guard

router = APIRouter(prefix="/debug", tags=["linkedin"])

@router.get("/linkedin-public")
def linkedin_public(slug: str = Query(...), li_at: Optional[str] = None):
    ua = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
          "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")
    tries = [
        f"https://www.linkedin.com/in/{slug}/",
        f"https://m.linkedin.com/in/{slug}/"
    ]
    with sync_playwright() as pw:
        b = pw.chromium.launch(headless=True)
        ctx = b.new_context(user_agent=ua, locale="en-US")
        if li_at:
            ctx.add_cookies([{"name":"li_at","value":li_at,"domain":".linkedin.com","path":"/","httpOnly":True,"secure":True}])
        p = ctx.new_page()
        for t in tries:
            p.goto(t, wait_until="domcontentloaded")
            if not any(k in p.url for k in ("/authwall", "/checkpoint", "/uas/login")):
                return {"ok": True, "final_url": p.url, "title": lk_title_guard.safe_title_sync(p)}
        return {"ok": False, "final_url": p.url, "title": lk_title_guard.safe_title_sync(p)}