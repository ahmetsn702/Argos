"""Instagram repository — tüm dış HTTP çağrıları burada."""
import time
import httpx
from typing import Optional
from app.repositories.base import BaseRepository
from app.core.config import IG_SESSIONID, IG_RETRY_MAX, IG_RETRY_BACKOFF_MS, REQUEST_TIMEOUT
from app.utils.common import ua

_APP_ID = "936619743392459"


class InstagramRepository(BaseRepository):
    def __init__(self):
        super().__init__(timeout=REQUEST_TIMEOUT, max_retries=IG_RETRY_MAX)

    def _ig_headers(self, username: str = "") -> dict:
        h = {**ua()}
        h.update({
            "X-IG-App-ID": _APP_ID,
            "Accept": "application/json",
            "X-Requested-With": "XMLHttpRequest",
            "Upgrade-Insecure-Requests": "1",
        })
        if username:
            h["Referer"] = f"https://www.instagram.com/{username}/"
        if IG_SESSIONID:
            h["Cookie"] = f"sessionid={IG_SESSIONID};"
        return h

    async def _retry_get(self, client: httpx.AsyncClient, url: str, params=None) -> Optional[httpx.Response]:
        last_exc = None
        for _ in range(max(1, IG_RETRY_MAX)):
            try:
                return await client.get(url, params=params, follow_redirects=True)
            except httpx.HTTPError as e:
                last_exc = e
                time.sleep(IG_RETRY_BACKOFF_MS / 1000.0)
        if last_exc:
            raise last_exc

    async def fetch_profile_api(self, username: str) -> dict:
        """web_profile_info API → dict with user data or {"status_code": N}."""
        url = "https://www.instagram.com/api/v1/users/web_profile_info/"
        params = {"username": username, "_": str(int(time.time()))}
        async with httpx.AsyncClient(headers=self._ig_headers(username), timeout=self.timeout, follow_redirects=True) as client:
            r = await self._retry_get(client, url, params=params)
        if r is None:
            return {"status_code": 0}
        if r.status_code == 200:
            try:
                return {"status_code": 200, "data": r.json()}
            except Exception:
                return {"status_code": 200, "data": {}}
        return {"status_code": r.status_code}

    async def fetch_profile_html(self, username: str) -> str:
        """instagram.com/{username}/ HTML sayfası."""
        url = f"https://www.instagram.com/{username}/"
        params = {"hl": "en", "_": str(int(time.time()))}
        async with httpx.AsyncClient(headers=self._ig_headers(username), timeout=self.timeout, follow_redirects=True) as client:
            r = await self._retry_get(client, url, params=params)
        return r.text if r and r.status_code == 200 else ""

    async def fetch_via_jina(self, username: str) -> str:
        """r.jina.ai proxy üzerinden IG sayfası."""
        url = f"https://r.jina.ai/http://www.instagram.com/{username}/"
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                r = await client.get(url)
                return r.text if r.status_code == 200 else ""
            except Exception:
                return ""

    async def fetch_media_html(self, username: str) -> str:
        """Medya listesi için public HTML."""
        url = f"https://www.instagram.com/{username}/"
        async with httpx.AsyncClient(timeout=self.timeout, follow_redirects=True) as client:
            try:
                r = await client.get(url, headers={"User-Agent": ua().get("User-Agent", "")})
                return r.text if r.status_code == 200 else ""
            except Exception:
                return ""

    async def search_by_name(self, name: str, limit: int = 10) -> list:
        """İsim tabanlı IG arama (public endpoint)."""
        url = "https://www.instagram.com/web/search/topsearch/"
        params = {"query": name, "context": "user", "count": min(limit, 20)}
        async with httpx.AsyncClient(headers=self._ig_headers(), timeout=self.timeout, follow_redirects=True) as client:
            try:
                r = await client.get(url, params=params)
                if r.status_code == 200:
                    j = r.json()
                    return j.get("users", [])
            except Exception:
                pass
        return []
