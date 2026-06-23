"""Base repository: async HTTP client with retry, timeout, error handling."""

import asyncio
import logging
from typing import Any, Dict, Optional

import httpx


class RepositoryError(Exception):
    """Base exception for repository layer."""
    pass


class RepositoryTimeout(RepositoryError):
    """Request timed out."""
    pass


class RepositoryRateLimited(RepositoryError):
    """429 Too Many Requests."""
    pass


class RepositoryServerError(RepositoryError):
    """5xx server error after all retries exhausted."""
    pass


class BaseRepository:
    def __init__(self, timeout: int = 20, max_retries: int = 3):
        self.timeout = timeout
        self.max_retries = max_retries
        self._client: Optional[httpx.AsyncClient] = None
        self.logger = logging.getLogger(self.__class__.__name__)

    async def __aenter__(self):
        self._client = httpx.AsyncClient(timeout=self.timeout)
        return self

    async def __aexit__(self, *exc):
        if self._client:
            await self._client.aclose()
            self._client = None

    def _get_client(self) -> httpx.AsyncClient:
        if self._client is None:
            self._client = httpx.AsyncClient(timeout=self.timeout)
        return self._client

    def _handle_response(self, resp: httpx.Response) -> Dict[str, Any]:
        if 200 <= resp.status_code < 300:
            return resp.json()
        if resp.status_code == 429:
            raise RepositoryRateLimited(f"429 rate limited: {resp.url}")
        if resp.status_code >= 500:
            raise RepositoryServerError(f"{resp.status_code}: {resp.url}")
        raise RepositoryError(f"{resp.status_code}: {resp.url}")

    async def _request(self, method: str, url: str, **kwargs) -> Dict[str, Any]:
        client = self._get_client()
        last_exc = None
        for attempt in range(self.max_retries):
            try:
                resp = await client.request(method, url, **kwargs)
                return self._handle_response(resp)
            except httpx.TimeoutException as e:
                last_exc = RepositoryTimeout(str(e))
            except RepositoryRateLimited:
                await asyncio.sleep(2 ** attempt)
                last_exc = RepositoryRateLimited(f"429 after {attempt + 1} attempts")
            except RepositoryServerError as e:
                last_exc = e
                if attempt < self.max_retries - 1:
                    await asyncio.sleep(2 ** attempt)
            except RepositoryError:
                raise
        raise last_exc

    async def _get(self, url: str, params: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        kwargs = {}
        if params:
            kwargs["params"] = params
        if headers:
            kwargs["headers"] = headers
        return await self._request("GET", url, **kwargs)

    async def _post(self, url: str, json: Optional[Dict] = None, headers: Optional[Dict] = None) -> Dict[str, Any]:
        kwargs = {}
        if json is not None:
            kwargs["json"] = json
        if headers:
            kwargs["headers"] = headers
        return await self._request("POST", url, **kwargs)
