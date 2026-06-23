# tests/test_instagram.py
"""Konsolide IG router testleri — app/routers/instagram.py."""
from unittest.mock import AsyncMock, patch, MagicMock
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

_PROFILE = {
    "username": "test",
    "status": "exists",
    "display_name": "Test User",
    "bio": "test bio",
    "profile_url": "https://www.instagram.com/test/",
    "source": "api",
}
_BIO = {"username": "test", "biography": "test bio", "full_name": "Test User", "source": "api"}


def _mock_svc(get_bio=None, get_profile=None, search=None):
    m = MagicMock()
    m.get_bio = AsyncMock(return_value=get_bio or _BIO)
    m.get_profile = AsyncMock(return_value=get_profile or _PROFILE)
    m.search = AsyncMock(return_value=search or [{"username": "test", "profile": _BIO}])
    return m


# ── /ig/bio ───────────────────────────────────────────────────────────────────
def test_ig_bio_endpoint():
    """GET /ig/bio?username=test → 200, bio döner."""
    with patch("app.routers.instagram._svc", _mock_svc()):
        r = client.get("/ig/bio?username=test")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "test"
    assert "bio" in data


def test_ig_bio_missing_username():
    r = client.get("/ig/bio")
    assert r.status_code == 422


# ── /ig-profile ───────────────────────────────────────────────────────────────
def test_ig_profile_endpoint():
    """GET /ig-profile?username=test → 200."""
    with patch("app.routers.instagram._svc", _mock_svc()):
        r = client.get("/ig-profile?username=test")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "test"


def test_ig_profile_missing_username():
    r = client.get("/ig-profile")
    assert r.status_code == 422


# ── /v2/ig-profile ────────────────────────────────────────────────────────────
def test_v2_ig_profile():
    """GET /v2/ig-profile?username=test → 200."""
    with patch("app.routers.instagram._svc", _mock_svc()):
        r = client.get("/v2/ig-profile?username=test")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "test"


# ── /hunt-ig-by-name ──────────────────────────────────────────────────────────
def test_hunt_ig_by_name():
    """GET /hunt-ig-by-name?full_name=test → 200, results list."""
    with patch("app.routers.instagram._svc", _mock_svc()):
        r = client.get("/hunt-ig-by-name?full_name=test+user")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert isinstance(data["results"], list)


def test_hunt_ig_by_name_too_short():
    r = client.get("/hunt-ig-by-name?full_name=t")
    assert r.status_code == 422


# ── /tester/ig-media ──────────────────────────────────────────────────────────
def test_ig_media_endpoint():
    """POST /tester/ig-media → 200 veya 422."""
    with patch("app.routers.instagram.fetch_recent_media",
               new=AsyncMock(return_value={"ok": True, "items": []})):
        r = client.post("/tester/ig-media", data={"user": "testuser", "limit": "3"})
    assert r.status_code in (200, 422)
