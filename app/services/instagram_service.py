import re, json, time, asyncio
import httpx
from typing import Dict
from bs4 import BeautifulSoup
from app.core.config import (IG_SESSIONID, IG_RETRY_MAX, IG_RETRY_BACKOFF_MS, REQUEST_TIMEOUT)
from app.utils.common import ua, clean_text

def _unescape_ig(s: str) -> str:
    if s is None:
        return ""
    try:
        return json.loads(f'"{s}"')
    except Exception:
        return s

def _extract_bio_from_html(html_text: str) -> Dict[str, str]:
    bio, full_name = "", ""
    m_bio = re.search(r'"biography"\\s*:\\s*"(.*?)"', html_text)
    if m_bio:
        bio = _unescape_ig(m_bio.group(1))
    m_full = re.search(r'"full_name"\\s*:\\s*"(.*?)"', html_text)
    if m_full:
        full_name = _unescape_ig(m_full.group(1))
    if not bio:
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            for tag in soup.find_all("script", {"type": "application/ld+json"}):
                try:
                    ld = json.loads(tag.string or "{}")
                    if isinstance(ld, dict):
                        desc = ld.get("description")
                        if desc and "Instagram photos" not in (desc or ""):
                            bio = desc
                            name = ld.get("name") or ld.get("alternateName")
                            if name:
                                full_name = name
                            break
                except Exception:
                    continue
        except Exception:
            pass
    if not bio:
        try:
            soup = BeautifulSoup(html_text, "html.parser")
            mdesc = soup.find("meta", attrs={"name": "description"})
            if mdesc and mdesc.has_attr("content"):
                candidate = (mdesc["content"] or "").strip()
                if "Instagram photos and videos" not in candidate:
                    bio = candidate
        except Exception:
            pass
    return {"biography": bio or "", "full_name": full_name or ""}

async def _try_get(client: httpx.AsyncClient, url: str, params=None, allow_redirects: bool = True) -> httpx.Response:
    last_exc = None
    for _ in range(IG_RETRY_MAX):
        try:
            return await client.get(url, params=params, follow_redirects=allow_redirects)
        except httpx.HTTPError as e:
            last_exc = e
            time.sleep(IG_RETRY_BACKOFF_MS / 1000.0)
    if last_exc:
        raise last_exc

async def get_instagram_bio(username: str) -> Dict[str, str]:
    headers = {**ua()}
    headers.update({
        "Referer": f"https://www.instagram.com/{username}/",
        "X-Requested-With": "XMLHttpRequest",
        "Accept": "application/json",
        "X-IG-App-ID": "936619743392459",
        "Upgrade-Insecure-Requests": "1",
    })
    if IG_SESSIONID:
        headers["Cookie"] = f"sessionid={IG_SESSIONID};"

    async with httpx.AsyncClient(headers=headers, timeout=REQUEST_TIMEOUT, follow_redirects=True) as client:
        # 1) JSON API
        try:
            r = await _try_get(client, "https://www.instagram.com/api/v1/users/web_profile_info/",
                               params={"username": username, "_": str(int(time.time()))})
            if r.status_code == 200:
                j = r.json()
                user = (j.get("data") or {}).get("user") or {}
                bio = user.get("biography") or ""
                full = user.get("full_name") or ""
                if bio or full:
                    return {"username": username, "full_name": full, "biography": bio, "source": "api"}
            elif r.status_code == 404:
                return {"error": "not_found"}
            elif r.status_code == 429:
                return {"error": "429"}
        except Exception:
            pass

        # 2) HTML
        try:
            r2 = await _try_get(client, f"https://www.instagram.com/{username}/",
                                params={"hl": "en", "_": str(int(time.time()))})
            if r2.status_code == 404:
                return {"error": "not_found"}
            if r2.status_code == 429:
                return {"error": "429"}
            ex = _extract_bio_from_html(r2.text or "")
            if ex.get("biography") or ex.get("full_name"):
                return {"username": username, "full_name": ex.get("full_name", ""), "biography": ex.get("biography", ""), "source": "html_en"}
        except Exception:
            pass

        # 3) r.jina.ai
        try:
            r3 = await _try_get(client, f"https://r.jina.ai/http://www.instagram.com/{username}/")
            if r3.status_code == 429:
                return {"error": "429"}
            if r3.status_code == 200 and r3.text:
                ex = _extract_bio_from_html(r3.text)
                if ex.get("biography") or ex.get("full_name"):
                    return {"username": username, "full_name": ex.get("full_name", ""), "biography": ex.get("biography", ""), "source": "jina_proxy"}
        except Exception:
            pass

    # 4) instagrapi fallback
    if IG_SESSIONID:
        try:
            from instagrapi import Client
            cl = Client()
            cl.login_by_sessionid(IG_SESSIONID)
            info = await asyncio.to_thread(cl.user_info_by_username, username)
            bio = getattr(info, "biography", "") or ""
            full = getattr(info, "full_name", "") or ""
            if bio or full:
                return {"username": username, "full_name": full, "biography": bio, "source": "instagrapi"}
        except Exception:
            pass

    return {"error": "unavailable"}

async def fetch_bio_instagram(username: str) -> Dict[str, str]:
    try:
        data = await get_instagram_bio(username)
        if "error" in data:
            if data["error"] == "not_found":
                return {"platform": "Instagram", "url": f"https://www.instagram.com/{username}/", "status": "not_found", "display_name": "", "bio": ""}
            if data["error"] == "429":
                return {"platform": "Instagram", "url": f"https://www.instagram.com/{username}/", "status": "429", "display_name": "", "bio": ""}
            return {"platform": "Instagram", "url": f"https://www.instagram.com/{username}/", "status": "unknown", "display_name": "", "bio": ""}
        bio = clean_text(data.get("biography", ""))
        name = clean_text(data.get("full_name", ""))
        status = "exists" if (bio or name) else "unknown"
        return {"platform": "Instagram", "url": f"https://www.instagram.com/{username}/", "status": status, "display_name": name, "bio": bio, "source": data.get("source")}
    except Exception:
        return {"platform": "Instagram", "url": f"https://www.instagram.com/{username}/", "status": "unknown", "display_name": "", "bio": ""}



import re as _re
import unicodedata as _unicodedata
from app.services.base import BaseService
from app.repositories.instagram_repo import InstagramRepository


def _fold_tr(s: str) -> str:
    s = (s or "").translate(str.maketrans("ıİşŞğĞçÇöÖüÜ", "iissggccoouu"))
    s = _unicodedata.normalize("NFKD", s)
    return "".join(c for c in s if not _unicodedata.combining(c)).lower()

def _no_vowels(s: str) -> str:
    return _re.sub(r"[aeiou]", "", s or "")

def _sanitize_ig(u: str) -> str:
    u = _fold_tr((u or "")).replace(" ", "")
    return _re.sub(r"[^a-z0-9._]", "", u)

def _gen_ig_candidates(full_name: str, limit: int = 40) -> list:
    toks = [_fold_tr(t) for t in _re.findall(r"[A-Za-zĞÜŞİÖÇğüşıöç]+", full_name or "") if t]
    if not toks:
        return []
    first = toks[0]; last = toks[-1] if len(toks) > 1 else ""
    fs, ls = _no_vowels(first) or first, _no_vowels(last) or last
    base = {
        f"{first}{last}", f"{first}.{last}", f"{first}_{last}",
        f"{first}{ls}", f"{fs}{ls}", f"{last}{first}", first, last, f"{fs}{last}",
        f"{first}t{ls}", f"{first}s{ls}", f"{first}ts{ls}",
    }
    more = set()
    for u in list(base):
        if "." in u: more.add(u.replace(".", "_"))
        if "_" in u: more.add(u.replace("_", "."))
    base |= more
    base = {_sanitize_ig(u) for u in base}
    cands = [u for u in base if u and _re.fullmatch(r"[a-z0-9._]{2,30}", u)]
    cands.sort(key=lambda u: (("." in u) * -1 + ("_" in u) * -1, len(u)))
    return cands[:limit]


class InstagramService(BaseService):
    def __init__(self):
        super().__init__(cache_ttl=300)
        self.repo = InstagramRepository()

    async def get_bio(self, username: str) -> dict:
        """Bio + profil bilgisi. Fallback: API → HTML → Jina."""
        key = self.cache_key("bio", username.lower())
        cached = await self.cache_get(key)
        if cached is not None:
            return cached
        result = await get_instagram_bio(username)
        await self.cache_set(key, result)
        return result

    async def get_profile(self, username: str) -> dict:
        """Birleşik profil (bio + meta). Cache'li."""
        key = self.cache_key("profile", username.lower())
        cached = await self.cache_get(key)
        if cached is not None:
            return cached
        bio_data = await get_instagram_bio(username)
        if "error" in bio_data:
            result = {"username": username, "status": bio_data["error"],
                      "display_name": "", "bio": "", "profile_url": f"https://www.instagram.com/{username}/"}
        else:
            result = {
                "username": username,
                "status": "exists" if (bio_data.get("biography") or bio_data.get("full_name")) else "unknown",
                "display_name": bio_data.get("full_name", ""),
                "bio": bio_data.get("biography", ""),
                "profile_url": f"https://www.instagram.com/{username}/",
                "source": bio_data.get("source"),
            }
        await self.cache_set(key, result)
        return result

    async def search(self, name: str, limit: int = 40) -> list:
        """İsimden IG handle adayları üret ve profillerini çek."""
        candidates = _gen_ig_candidates(name, limit=limit)
        results = []
        for u in candidates:
            prof = await get_instagram_bio(u)
            results.append({"username": u, "profile": prof})
        return results


# Modül-seviyesi singleton — router'lar bunu kullanır
_service = InstagramService()

async def get_ig_service() -> InstagramService:
    return _service
