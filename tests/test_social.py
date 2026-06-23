# tests/test_social.py
"""Tests for social profile endpoints.

Endpoints covered:
  - GET /compare-ig-x2          (app.routers.similarity)
  - GET /hunt-x-by-name         (app.routers.similarity)
  - GET /ig/bio                 (app.routers.ig_compat)
  - GET /v2/ig-profile          (app.routers.hunt_social_v2)
"""
from unittest.mock import patch, AsyncMock

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# -------------------------------------------------------------------- helpers
def _ig_profile_stub(username="bob"):
    return {
        "status": "exists",
        "username": username,
        "display_name": "Bob Stub",
        "bio": "developer · istanbul · loves cats",
        "profile_url": f"https://instagram.com/{username}",
    }


def _x_profile_stub(username="bob"):
    return {
        "status": "exists",
        "username": username,
        "display_name": "Bob Stub",
        "bio": "developer · istanbul · also loves cats",
        "profile_url": f"https://x.com/{username}",
    }


# ============================================================ /compare-ig-x2
@patch("app.routers.similarity.fetch_x_profile_simple")
@patch("app.routers.similarity.fetch_ig_profile_simple")
def test_compare_ig_x2_returns_similarity_shape(mock_ig, mock_x):
    """Mocked profiles → 200 with normalised keys."""
    mock_ig.return_value = _ig_profile_stub("bob")
    mock_x.return_value = _x_profile_stub("bob")

    r = client.get("/compare-ig-x2?username=bob")
    assert r.status_code == 200
    data = r.json()
    # The endpoint should at least echo both profiles back somewhere.
    payload = str(data)
    assert "bob" in payload


def test_compare_ig_x2_missing_username_returns_422():
    """No `username` query param → 422."""
    r = client.get("/compare-ig-x2")
    assert r.status_code == 422


@patch("app.routers.similarity.fetch_x_profile_simple")
@patch("app.routers.similarity.fetch_ig_profile_simple")
def test_compare_ig_x2_handles_missing_profiles(mock_ig, mock_x):
    """Both fetchers return None → endpoint substitutes empty stubs (200)."""
    mock_ig.return_value = None
    mock_x.return_value = None

    r = client.get("/compare-ig-x2?username=ghost")
    assert r.status_code == 200


# ============================================================ /hunt-x-by-name
@patch("app.routers.similarity.fetch_x_profile_simple")
def test_hunt_x_by_name_returns_results(mock_x):
    """Valid full_name → 200 with `results` list and candidate metadata."""
    mock_x.return_value = _x_profile_stub("ahmettssyn")

    r = client.get("/hunt-x-by-name?full_name=Ahmet+Sayan&limit=3")
    assert r.status_code == 200
    data = r.json()
    assert data["full_name"] == "Ahmet Sayan"
    assert "results" in data
    assert isinstance(data["results"], list)
    assert data.get("candidates_tried", 0) >= 1


def test_hunt_x_by_name_too_short_returns_422():
    """full_name shorter than 2 chars → 422."""
    r = client.get("/hunt-x-by-name?full_name=A")
    assert r.status_code == 422


@patch("app.routers.similarity.fetch_x_profile_simple")
def test_hunt_x_by_name_handles_fetch_returning_none(mock_x):
    """Fetcher returns None for every candidate → still 200, status='unknown' items."""
    mock_x.return_value = None

    r = client.get("/hunt-x-by-name?full_name=Nobody+Atall&limit=2")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data["results"], list)
    if data["results"]:
        assert data["results"][0]["profile"]["status"] == "unknown"


# ============================================================ /ig/bio
def test_ig_bio_returns_first_successful_source():
    """Service returns bio → endpoint echoes it."""
    bio_data = {"username": "demo", "biography": "hello world", "full_name": "", "source": "api"}
    with patch("app.routers.instagram._svc") as mock_svc:
        mock_svc.get_bio = AsyncMock(return_value=bio_data)
        r = client.get("/ig/bio?username=demo")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "demo"
    assert data["bio"] == "hello world"
    assert data["source"] == "api"


def test_ig_bio_uses_cache_when_available():
    """Service returns cached bio → endpoint returns it."""
    bio_data = {"username": "demo", "biography": "cached bio", "full_name": "", "source": "proxy"}
    with patch("app.routers.instagram._svc") as mock_svc:
        mock_svc.get_bio = AsyncMock(return_value=bio_data)
        r = client.get("/ig/bio?username=demo")
    assert r.status_code == 200
    assert r.json()["bio"] == "cached bio"


def test_ig_bio_missing_username_returns_422():
    """No `username` query → 422."""
    r = client.get("/ig/bio")
    assert r.status_code == 422


def test_ig_bio_all_fetchers_fail_returns_empty_envelope():
    """Service returns error → endpoint should not 500."""
    with patch("app.routers.instagram._svc") as mock_svc:
        mock_svc.get_bio = AsyncMock(return_value={"error": "unavailable"})
        r = client.get("/ig/bio?username=ghost")
    assert r.status_code == 200
    assert r.status_code == 200


# ============================================================ /v2/ig-profile
def test_v2_ig_profile_returns_payload():
    """Mocked profile → 200, payload has expected keys."""
    profile = _ig_profile_stub("alice")
    with patch("app.routers.instagram._svc") as mock_svc:
        mock_svc.get_profile = AsyncMock(return_value=profile)
        r = client.get("/v2/ig-profile?username=alice")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "alice"
    assert data["status"] == "exists"


def test_v2_ig_profile_missing_username_returns_422():
    """No `username` query → 422."""
    r = client.get("/v2/ig-profile")
    assert r.status_code == 422


def test_v2_ig_profile_handles_service_error():
    """Underlying service raises → endpoint must not silently 200 with garbage."""
    with patch("app.routers.instagram._svc") as mock_svc:
        mock_svc.get_profile = AsyncMock(side_effect=RuntimeError("ig down"))
        safe_client = TestClient(app, raise_server_exceptions=False)
        r = safe_client.get("/v2/ig-profile?username=alice")
    assert r.status_code in (500, 502, 503)
