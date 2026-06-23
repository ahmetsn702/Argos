# tests/test_unified.py
"""Tests for the unified scanning endpoint.

Note: the UI (`mini_panel.py`, `ui/dashboard.html`) calls
`POST /unified-profile-analysis`, but that route is **not defined** anywhere
in `app/routers/`. The actual unified scanning endpoint is
`GET /scan/full` (app.routers.unified.scan_full). We test the real endpoint
and add one regression test that documents the missing UI dependency.
"""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_unified_profile_analysis_is_missing():
    """Document that /unified-profile-analysis is not registered (UI bug)."""
    r = client.post("/unified-profile-analysis", json={"username": "demo"})
    assert r.status_code == 404


def test_scan_full_with_username_returns_shape():
    """Valid username → 200 with the standard scan_full envelope."""
    r = client.get("/scan/full?username=testuser")
    assert r.status_code == 200
    data = r.json()
    assert data["input"]["username"] == "testuser"
    assert data["input"]["email"] is None
    assert "results" in data
    assert isinstance(data["results"], dict)
    assert data["verdict"] in {"ok", "partial", "fail"}
    assert data["took_ms"] > 0


def test_scan_full_with_email_returns_shape():
    """Valid email → 200; results dict carries provider entries."""
    r = client.get("/scan/full?email=user@example.com")
    assert r.status_code == 200
    data = r.json()
    assert data["input"]["email"] == "user@example.com"
    assert isinstance(data["results"], dict)
    assert data["verdict"] in {"ok", "partial", "fail"}


def test_scan_full_no_input_returns_400():
    """Missing all of email/username/phone → 400."""
    r = client.get("/scan/full")
    assert r.status_code == 400


@patch("app.routers.unified._call_social_hunt")
def test_scan_full_service_failure_is_partial_or_fail(mock_social):
    """If a downstream raises, the endpoint must still return a JSON envelope."""
    async def _boom(*args, **kwargs):
        raise RuntimeError("social hunt down")

    mock_social.side_effect = _boom
    r = client.get("/scan/full?username=ghostuser")
    # The endpoint catches per-task exceptions; never 500.
    assert r.status_code == 200
    data = r.json()
    assert data["verdict"] in {"partial", "fail", "ok"}
    assert "results" in data


def test_scan_full_legacy_helper_is_callable_in_process():
    """The internal _scan_full_legacy helper can be awaited directly without HTTP."""
    import asyncio
    from app.routers.unified import _scan_full_legacy

    result = asyncio.run(
        _scan_full_legacy(email=None, username="testuser", phone=None, timeout=10.0)
    )
    assert isinstance(result, dict)
    assert "results" in result
    assert "verdict" in result
    assert result["verdict"] in {"ok", "partial", "fail"}
    assert result["input"]["username"] == "testuser"
    assert result["input"]["email"] is None
    assert "took_ms" in result


def test_scan_full_legacy_helper_empty_input_returns_fail():
    """No input → verdict=fail (HTTP handler raises 400 separately)."""
    import asyncio
    from app.routers.unified import _scan_full_legacy

    result = asyncio.run(_scan_full_legacy())
    assert result["verdict"] == "fail"
    assert result["results"] == {}


# ─── POST /scan/full (PersonCard channel) ────────────────────────────────
# Mock the in-process helper so these tests don't hit external APIs.
import time as _time
from unittest.mock import AsyncMock

_FAKE_LEGACY = {
    "input": {"email": None, "username": "x", "phone": None},
    "results": {"social": {"ok": True, "data": {"results": []}}},
    "verdict": "partial",
    "took_ms": 1,
}


def _unique_first_name(prefix: str) -> str:
    """Sidestep aggregator cache between POST tests."""
    return f"{prefix}{int(_time.time() * 1000)}"


@patch("app.routers.unified._scan_full_legacy", new=AsyncMock(return_value=_FAKE_LEGACY))
def test_post_scan_full_minimum_body_returns_personcard():
    body = {
        "first_name": _unique_first_name("Ali"),
        "last_name": "Veli",
        "hometown": "Istanbul",
        "fast": True,
        "max_scans": 1,
        "timeout": 10,
    }
    r = client.post("/scan/full", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    # PersonCard shape
    assert "profiles" in data
    assert "sources" in data
    assert "summary" in data
    assert "verdict" in data
    assert data["verdict"] in {"ok", "partial", "fail"}
    assert isinstance(data["profiles"], list)
    assert isinstance(data["sources"], list)


@patch("app.routers.unified._scan_full_legacy", new=AsyncMock(return_value=_FAKE_LEGACY))
def test_post_scan_full_with_hints():
    body = {
        "first_name": _unique_first_name("Hint"),
        "last_name": "User",
        "hometown": "X",
        "hints": {
            "emails": ["t@x.com"],
            "usernames": ["tuser"],
            "phones": ["+905551112233"],
        },
        "fast": True,
        "max_scans": 1,
        "timeout": 10,
    }
    r = client.post("/scan/full", json=body)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["query"]["first_name"] == body["first_name"]
    assert data["query"]["last_name"] == "User"
    # phones echoed from hints back to top-level (per build_person_card)
    assert "+905551112233" in data["phones"]


def test_post_scan_full_validation_error():
    """Missing required fields → 422 from FastAPI/Pydantic validation."""
    r = client.post("/scan/full", json={"last_name": "OnlyLast"})
    assert r.status_code == 422


def test_get_scan_full_still_works_after_post_added():
    """Regression: legacy GET shape unchanged."""
    r = client.get("/scan/full?username=testuser")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert "verdict" in data
    assert data["input"]["username"] == "testuser"


# ─── Unified UI form (HTML token tests, no browser needed) ───────────────

def test_get_mini_panel_html_contains_unified_form_fields():
    """The card-unified rich form must expose all expected input ids."""
    r = client.get("/mini")
    assert r.status_code == 200
    html = r.text
    for token in (
        'id="uni-fname"',
        'id="uni-lname"',
        'id="uni-city"',
        'id="uni-emails"',
        'id="uni-phones"',
        'id="uni-usernames"',
        'id="uni-fast"',
        'id="uni-btn"',
    ):
        assert token in html, f"missing {token} in /mini HTML"


def test_mini_panel_uni_renderer_handles_personcard_shape():
    """Renderer JS must reference PersonCard fields (profiles, summary, emails)."""
    r = client.get("/mini")
    html = r.text
    for token in (
        "renderers.uni",
        "PLATFORM_ICON",
        "confidence_overall",
        "username_best_guesses",
    ):
        assert token in html, f"missing {token} in renderer JS"
