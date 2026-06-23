# tests/test_linkedin.py
"""Tests for /linkedin-bio endpoint (app.routers.linkedin)."""
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


_HTML = """
<html>
<head>
  <meta property="og:title" content="Jane Doe – Senior Engineer at Acme">
  <meta property="og:description" content="10+ years building scalable systems.">
</head>
<body></body>
</html>
"""


def _mock_httpx_client(text: str, status: int = 200):
    resp = MagicMock()
    resp.text = text
    resp.status_code = status
    async_client = AsyncMock()
    async_client.get = AsyncMock(return_value=resp)
    async_client.__aenter__ = AsyncMock(return_value=async_client)
    async_client.__aexit__ = AsyncMock(return_value=False)
    mock_class = MagicMock(return_value=async_client)
    return mock_class


def test_linkedin_bio_parses_og_metadata():
    """Valid /in/ URL → 200 with profile_name + headline parsed from og: meta."""
    with patch("app.routers.linkedin.httpx.AsyncClient", _mock_httpx_client(_HTML)):
        r = client.get("/linkedin-bio?url=https://www.linkedin.com/in/janedoe/")

    assert r.status_code == 200
    data = r.json()
    assert "Jane Doe" in data["profile_name"]
    assert "10+ years" in data["headline"]
    assert data["url"] == "https://www.linkedin.com/in/janedoe/"
    assert data["source"] == "public_fallback"


def test_linkedin_bio_normalises_url():
    """`linkedin.com/in/x` (no scheme, no www) → upgraded to canonical form."""
    with patch("app.routers.linkedin.httpx.AsyncClient", _mock_httpx_client(_HTML)):
        r = client.get("/linkedin-bio?url=linkedin.com/in/janedoe")

    assert r.status_code == 200
    assert r.json()["url"] == "https://www.linkedin.com/in/janedoe/"


def test_linkedin_bio_rejects_non_profile_url():
    """URL without `/in/` → 400."""
    r = client.get("/linkedin-bio?url=https://www.linkedin.com/company/acme/")
    assert r.status_code == 400


def test_linkedin_bio_missing_url_returns_422():
    """No `url` query param → 422."""
    r = client.get("/linkedin-bio")
    assert r.status_code == 422


def test_linkedin_bio_request_failure_returns_graceful_envelope():
    """httpx raising → 200 with empty fields and a `note`."""
    async_client = AsyncMock()
    async_client.get = AsyncMock(side_effect=ConnectionError("dns fail"))
    async_client.__aenter__ = AsyncMock(return_value=async_client)
    async_client.__aexit__ = AsyncMock(return_value=False)
    mock_class = MagicMock(return_value=async_client)

    with patch("app.routers.linkedin.httpx.AsyncClient", mock_class):
        r = client.get("/linkedin-bio?url=https://www.linkedin.com/in/janedoe/")

    assert r.status_code == 200
    data = r.json()
    assert data["profile_name"] == ""
    assert data["headline"] == ""
    assert data["source"] == "public_fallback"
    assert "note" in data
