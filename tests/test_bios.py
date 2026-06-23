# tests/test_bios.py
"""Tests for /username-bios endpoint (app.routers.bios)."""
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _make_fetcher(platform: str, status: str = "exists", bio: str = "demo bio"):
    """Return a stub fetcher matching the FETCHERS contract: (username, session) -> dict."""
    def _fn(username, session):
        return {
            "platform": platform,
            "url": f"https://{platform.lower()}.com/{username}",
            "status": status,
            "display_name": f"{platform} User",
            "bio": bio,
        }
    return _fn


def _all_fetchers():
    return {
        "x": _make_fetcher("X"),
        "github": _make_fetcher("Github"),
        "reddit": _make_fetcher("Reddit"),
        "youtube": _make_fetcher("Youtube", status="not_found", bio=""),
        "instagram": _make_fetcher("Instagram"),
    }


def test_bios_returns_platforms():
    """Valid input → 200 with all 5 platforms in `results`."""
    with patch.dict("app.routers.bios.FETCHERS", _all_fetchers(), clear=True):
        r = client.get("/username-bios?username=testuser")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "testuser"
    assert data["count"] == 5
    assert isinstance(data["results"], list)
    assert len(data["results"]) == 5
    platforms = {item["platform"] for item in data["results"]}
    assert platforms == {"X", "Github", "Reddit", "Youtube", "Instagram"}


def test_bios_only_filter_narrows_results():
    """`only=instagram,github` → only those two platforms returned."""
    with patch.dict("app.routers.bios.FETCHERS", _all_fetchers(), clear=True):
        r = client.get("/username-bios?username=testuser&only=instagram,github")
    assert r.status_code == 200
    data = r.json()
    platforms = {item["platform"] for item in data["results"]}
    assert platforms == {"Instagram", "Github"}
    assert data["count"] == 2


def test_bios_strips_at_prefix():
    """Leading `@` should be stripped from the username in the response."""
    with patch.dict("app.routers.bios.FETCHERS", _all_fetchers(), clear=True):
        r = client.get("/username-bios?username=@bob")
    assert r.status_code == 200
    assert r.json()["username"] == "bob"


def test_bios_missing_username():
    """No `username` query param → 422 (FastAPI validation)."""
    r = client.get("/username-bios")
    assert r.status_code == 422


def test_bios_fetcher_error_falls_back_gracefully():
    """A fetcher that raises must not bubble up — it yields an `unknown` item."""
    def _broken(username, session):
        raise RuntimeError("network down")

    fetchers = _all_fetchers()
    fetchers["github"] = _broken

    with patch.dict("app.routers.bios.FETCHERS", fetchers, clear=True):
        r = client.get("/username-bios?username=testuser")

    assert r.status_code == 200
    data = r.json()
    assert data["count"] == 5
    github_item = next((it for it in data["results"] if it["platform"] == "Github"), None)
    assert github_item is not None
    assert github_item["status"] == "unknown"
    assert github_item["bio"] == ""
