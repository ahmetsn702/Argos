"""Smoke tests for async-migrated endpoints."""
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _mock_httpx(json_data=None, status=200, text=""):
    resp = MagicMock()
    resp.status_code = status
    resp.text = text
    resp.json = MagicMock(return_value=json_data or {})
    ac = AsyncMock()
    ac.get = AsyncMock(return_value=resp)
    ac.post = AsyncMock(return_value=resp)
    ac.__aenter__ = AsyncMock(return_value=ac)
    ac.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=ac)


def test_combined_search_no_key():
    """GET /combined-search-v1 without API key returns 200 with empty results."""
    import app.routers.search as search_mod
    orig_key = search_mod.API_KEY
    orig_cx = search_mod.CX
    try:
        search_mod.API_KEY = ""
        search_mod.CX = ""
        r = client.post("/combined-search-v1?name=test")
        assert r.status_code == 200
        assert r.json()["text_search_count"] == 0
    finally:
        search_mod.API_KEY = orig_key
        search_mod.CX = orig_cx


def test_linkedin_bio_invalid():
    """GET /linkedin-bio with a non-/in/ URL returns 400."""
    r = client.get("/linkedin-bio?url=https://www.linkedin.com/company/acme/")
    assert r.status_code == 400


def test_fb_profile():
    """GET /fb-profile returns 200 with expected keys."""
    mock_cls = _mock_httpx(status=404, text="<html><title>Not Found</title></html>")
    with patch("app.services.fb_service.httpx.AsyncClient", mock_cls):
        r = client.get("/fb-profile?username=testuser")
    assert r.status_code == 200
    data = r.json()
    assert "username" in data
    assert "status" in data


def test_fb_photos():
    """GET /fb-photos returns 200 with expected keys."""
    mock_cls = _mock_httpx(status=404, text="<html></html>")
    with patch("app.services.fb_photos.httpx.AsyncClient", mock_cls):
        r = client.get("/fb-photos?username=testuser&limit=3")
    assert r.status_code == 200
    data = r.json()
    assert "username" in data
    assert "photos" in data
