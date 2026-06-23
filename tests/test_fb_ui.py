# tests/test_fb_ui.py
"""FB UI router + FbDumpService smoke testleri."""
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# ── /fb-profile ───────────────────────────────────────────────────────────────
def test_fb_profile_endpoint():
    """GET /fb-profile?username=test → 200."""
    profile = {"status": "exists", "username": "test", "display_name": "Test",
               "bio": "bio", "profile_pic": "", "profile_url": "https://facebook.com/test", "meta": {}}
    with patch("app.routers.facebook.get_fb_profile", new=AsyncMock(return_value=profile)):
        r = client.get("/fb-profile?username=test")
    assert r.status_code == 200
    assert r.json()["username"] == "test"


# ── /fb-photos ────────────────────────────────────────────────────────────────
def test_fb_photos_endpoint():
    """GET /fb-photos?username=test → 200."""
    photos = {"username": "test", "photos": [], "count": 0, "meta": {}}
    with patch("app.routers.facebook.get_fb_photos", new=AsyncMock(return_value=photos)):
        r = client.get("/fb-photos?username=test")
    assert r.status_code == 200
    assert r.json()["username"] == "test"


# ── /fb (UI HTML) ─────────────────────────────────────────────────────────────
def test_fb_ui_html():
    """GET /fb → 200, HTML response."""
    import os
    from pathlib import Path
    html_path = str(Path(__file__).resolve().parent.parent / "ui" / "fb_ui.html")
    if os.path.exists(html_path):
        r = client.get("/fb")
        assert r.status_code == 200
        assert "text/html" in r.headers.get("content-type", "")


# ── FbDumpService ─────────────────────────────────────────────────────────────
def test_fb_dump_service_run_dump():
    """FbDumpService.run_dump() → dict döner, crash yok."""
    import asyncio
    from app.services.fb_dump_service import FbDumpService
    svc = FbDumpService()
    mock_proc = MagicMock()
    mock_proc.returncode = 0
    mock_proc.stdout = '{"saved": 3}'
    mock_proc.stderr = ""
    with patch("subprocess.run", return_value=mock_proc):
        with patch("pathlib.Path.mkdir"):
            result = asyncio.get_event_loop().run_until_complete(
                svc.run_dump("testuser", limit=5)
            )
    assert isinstance(result, dict)
    assert "returncode" in result
    assert result["returncode"] == 0
