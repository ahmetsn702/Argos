import os
import httpx
from app.main import app

def get_client() -> httpx.AsyncClient:
    api_url = os.getenv("ARGOS_API_URL")
    if api_url:
        return httpx.AsyncClient(base_url=api_url.rstrip("/"), timeout=30.0)
    else:
        try:
            return httpx.AsyncClient(app=app, base_url="http://test", timeout=30.0)
        except TypeError:
            from httpx import ASGITransport
            return httpx.AsyncClient(transport=ASGITransport(app=app), base_url="http://test", timeout=30.0)

