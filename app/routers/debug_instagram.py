from fastapi import APIRouter, Query
import time, requests
from app.utils.common import ua
from app.core.config import REQUEST_TIMEOUT

router = APIRouter(prefix="/debug", tags=["debug-instagram"])

@router.get("/instagram")
def debug_instagram(username: str = Query(...)):
    uname = username.strip().lstrip("@")
    s = requests.Session(); s.headers.update(ua())
    tries = []
    def _timeit(name, fn):
        t0 = time.time()
        ok = False
        try: ok = fn()
        except Exception: ok = False
        ms = int((time.time() - t0) * 1000)
        tries.append({"step": name, "ok": ok, "ms": ms})

    def step_api():
        r = s.get("https://www.instagram.com/api/v1/users/web_profile_info/",
                  params={"username": uname, "_": str(int(time.time()))},
                  timeout=REQUEST_TIMEOUT)
        return (r.status_code == 200 and '"biography"' in (r.text or ""))

    def step_html():
        r = s.get(f"https://www.instagram.com/{uname}/", params={"hl":"en"}, timeout=REQUEST_TIMEOUT, allow_redirects=True)
        return (r.status_code != 404) and ('"biography"' in (r.text or "") or "application/ld+json" in (r.text or ""))

    def step_jina():
        r = s.get(f"https://r.jina.ai/http://www.instagram.com/{uname}/", timeout=REQUEST_TIMEOUT+5)
        return (r.status_code == 200 and '"biography"' in (r.text or ""))

    _timeit("api", step_api)
    _timeit("html_en", step_html)
    _timeit("jina_http", step_jina)
    return {"username": uname, "tries": tries}
