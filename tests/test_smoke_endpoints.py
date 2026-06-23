# tests/test_smoke_endpoints.py
"""Smoke testleri — status code ve response shape kontrolü. Dış HTTP mock'lanmış."""
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

_SCAN_RESULT = {"platform": "GitHub", "url": "https://github.com/test",
                "status": "exists", "http_status": 200, "final_url": "https://github.com/test"}
_BIO_DATA = {"username": "test", "biography": "bio", "full_name": "Test", "source": "api"}
_PROFILE = {"username": "test", "status": "exists", "display_name": "Test",
            "bio": "bio", "profile_url": "https://www.instagram.com/test/"}


# ── Scan ─────────────────────────────────────────────────────────────────────
def test_username_scan():
    with patch("app.services.scan_service.probe_single", new=AsyncMock(return_value=_SCAN_RESULT)):
        r = client.get("/username-scan?username=test")
    assert r.status_code == 200
    assert "results" in r.json()


def test_username_scan_empty():
    r = client.get("/username-scan")
    assert r.status_code == 422


# ── Instagram ─────────────────────────────────────────────────────────────────
def test_ig_bio():
    with patch("app.routers.instagram._svc") as m:
        m.get_bio = AsyncMock(return_value=_BIO_DATA)
        r = client.get("/ig/bio?username=test")
    assert r.status_code == 200


def test_ig_profile():
    with patch("app.routers.instagram._svc") as m:
        m.get_profile = AsyncMock(return_value=_PROFILE)
        r = client.get("/ig-profile?username=test")
    assert r.status_code == 200


def test_hunt_ig():
    with patch("app.routers.instagram._svc") as m:
        m.search = AsyncMock(return_value=[])
        r = client.get("/hunt-ig-by-name?full_name=test+user")
    assert r.status_code == 200


# ── Search & Media ────────────────────────────────────────────────────────────
def test_combined_search():
    with patch("app.routers.media.text_search_google", new=AsyncMock(return_value=[])):
        r = client.post("/combined-search?name=test")
    assert r.status_code == 200


def test_photos():
    with patch("app.routers.photos.collect_photos", new=AsyncMock(return_value={"photos": [], "count": 0})):
        r = client.get("/photos?username=test")
    assert r.status_code == 200


# ── Compare ───────────────────────────────────────────────────────────────────
def test_compare_ig_x2():
    with patch("app.routers.similarity.fetch_ig_profile_simple",
               new=AsyncMock(return_value={"status": "exists", "username": "test", "bio": "", "display_name": ""})), \
         patch("app.routers.similarity.fetch_x_profile_simple",
               return_value={"status": "exists", "username": "test", "bio": "", "display_name": ""}):
        r = client.get("/compare-ig-x2?username=test")
    assert r.status_code == 200


# ── Mosint ────────────────────────────────────────────────────────────────────
def test_mosint_full():
    empty = AsyncMock(return_value={"ok": False})
    with patch("app.routers.mosint_api.get_emailrep", empty), \
         patch("app.routers.mosint_api.doh_mx", empty), \
         patch("app.routers.mosint_api.gravatar_info", empty), \
         patch("app.routers.mosint_api.openpgp_lookup", empty), \
         patch("app.routers.mosint_api.abstract_email_lookup", empty):
        r = client.get("/mosint/full?email=a@b.com")
    assert r.status_code == 200
    assert isinstance(r.json(), dict)


# ── Debug ─────────────────────────────────────────────────────────────────────
def test_routes():
    r = client.get("/__routes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)
    assert len(r.json()) > 0


def test_ping():
    r = client.get("/__ping")
    assert r.status_code == 200
    assert r.json().get("ok") is True
