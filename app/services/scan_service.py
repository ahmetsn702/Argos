from dataclasses import dataclass
from typing import List, Dict
import httpx
from bs4 import BeautifulSoup
from app.utils.common import ua

@dataclass
class Platform:
    name: str
    url_tmpl: str
    not_found_signatures: List[str]
    login_hosts: List[str] = None
    require_name_in_title: bool = False

PLATFORMS: List[Platform] = [
    Platform("Instagram","https://www.instagram.com/{u}/",["Sorry, this page isn't available.","Bu Sayfa Kullanılamıyor","Page Not Found"],login_hosts=["www.instagram.com"],require_name_in_title=True),
    Platform("X (Twitter)","https://x.com/{u}",["This account doesn't exist","Account suspended"],login_hosts=["x.com","twitter.com"],require_name_in_title=True),
    Platform("TikTok","https://www.tiktok.com/@{u}",["Couldn't find this account","Page not available","This account is suspended"],login_hosts=["www.tiktok.com"],require_name_in_title=True),
    Platform("GitHub","https://github.com/{u}",["Not Found","Create your own GitHub profile"],login_hosts=["github.com"],require_name_in_title=True),
    Platform("Reddit","https://www.reddit.com/user/{u}/",["page not found","Sorry, nobody on Reddit goes by"],login_hosts=["www.reddit.com"]),
    Platform("YouTube","https://www.youtube.com/@{u}",["This channel does not exist","Channel not found"],login_hosts=["www.youtube.com"],require_name_in_title=True),
    Platform("Threads","https://www.threads.net/@{u}",["Content Not Found","Page Not Found"],login_hosts=["www.threads.net"],require_name_in_title=True),
]

def _extract_basic_meta(html: str) -> Dict[str, str]:
    try:
        soup = BeautifulSoup(html, "html.parser")
    except Exception:
        return {}
    out = {}
    t = soup.title.string.strip() if soup.title and soup.title.string else ""
    out["title"] = t
    og_url = soup.find("meta", property="og:url"); og_title = soup.find("meta", property="og:title")
    out["og:url"] = og_url["content"].strip() if og_url and og_url.has_attr("content") else ""
    out["og:title"] = og_title["content"].strip() if og_title and og_title.has_attr("content") else ""
    can = soup.find("link", rel=lambda v: v and "canonical" in v)
    out["canonical"] = can["href"].strip() if can and can.has_attr("href") else ""
    return out

def _looks_like_login_or_discover(final_url: str, platform: Platform) -> bool:
    if not final_url:
        return False
    url_l = final_url.lower()
    suspicious_paths = ["login", "i/flow/login", "/discover", "/signup", "/sessions", "/accounts/login"]
    if any(p in url_l for p in suspicious_paths):
        return True
    if platform.login_hosts:
        if any(h in url_l for h in platform.login_hosts) and any(p in url_l for p in suspicious_paths):
            return True
    return False

def _username_in_text(u: str, *texts: str) -> bool:
    u = u.lower().lstrip("@")
    return any((u in (t or "").lower()) for t in texts if t)

def _validate_html_existence(username: str, platform: Platform, response: httpx.Response) -> str:
    status = response.status_code
    text = (response.text or "")
    final_url = str(response.url) if response.url else ""
    if any(sig and sig.lower() in text.lower() for sig in platform.not_found_signatures):
        return "not_found"
    if _looks_like_login_or_discover(final_url, platform):
        return "unknown"
    meta = _extract_basic_meta(text)
    title = meta.get("title", ""); og_url = meta.get("og:url", ""); og_title = meta.get("og:title", ""); canonical = meta.get("canonical", "")
    strong_url_hit = _username_in_text(username, og_url, canonical)
    if platform.require_name_in_title:
        if _username_in_text(username, title, og_title, og_url, canonical):
            if status in (200, 301, 302, 303, 307, 308):
                return "exists"
        return "unknown"
    if strong_url_hit and status in (200, 301, 302, 303, 307, 308):
        return "exists"
    if status == 404:
        return "not_found"
    return "unknown"

async def probe_single(username: str, p: Platform) -> Dict[str, str]:
    url = p.url_tmpl.format(u=username)
    try:
        async with httpx.AsyncClient(headers=ua(), follow_redirects=True, timeout=15) as client:
            r = await client.get(url)
        verdict = _validate_html_existence(username, p, r)
        return {"platform": p.name, "url": url, "status": verdict, "http_status": r.status_code, "final_url": str(r.url)}
    except httpx.HTTPError:
        return {"platform": p.name, "url": url, "status": "unknown", "http_status": None, "final_url": None}
