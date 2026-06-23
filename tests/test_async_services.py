# tests/test_async_services.py
"""Karakteristik testler — async geçiş sonrası smoke tests.

TestClient sync çalışır, pytest-asyncio gerekmez.
Tüm dış HTTP çağrıları mock'lanır.
"""
from unittest.mock import AsyncMock, patch, MagicMock
import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


# --- helpers ------------------------------------------------------------------
def _probe_result(platform="GitHub"):
    return {"platform": platform, "url": f"https://x.com/test", "status": "exists",
            "http_status": 200, "final_url": f"https://x.com/test"}


# =============================================================================
# test_scan_parallel: /username-scan?username=test → 200, "results" key var
# =============================================================================
def test_scan_parallel():
    """/username-scan → 200, results list döner, crash yok."""
    with patch("app.services.scan_service.probe_single",
               new=AsyncMock(return_value=_probe_result())):
        r = client.get("/username-scan?username=test")
    assert r.status_code == 200
    data = r.json()
    assert "results" in data
    assert isinstance(data["results"], list)
    assert data["username"] == "test"


# =============================================================================
# test_mosint_no_key: /mosint/full?email=test@test.com → 200, dict döner
# =============================================================================
def test_mosint_no_key():
    """/mosint/full → 200, api key yokken bile crash olmamalı."""
    # Tüm dış çağrıları kısa-devre et
    empty = AsyncMock(return_value={"ok": False})
    with patch("app.routers.mosint_api.get_emailrep", empty), \
         patch("app.routers.mosint_api.doh_mx", empty), \
         patch("app.routers.mosint_api.gravatar_info", empty), \
         patch("app.routers.mosint_api.openpgp_lookup", empty), \
         patch("app.routers.mosint_api.abstract_email_lookup", empty):
        r = client.get("/mosint/full?email=test@test.com")
    assert r.status_code == 200
    data = r.json()
    assert isinstance(data, dict)
    assert "email" in data


# =============================================================================
# test_ig_compat: /ig/bio?username=instagram → 200
# =============================================================================
def test_ig_compat():
    """/ig/bio → 200, service'ten bio döner."""
    bio_data = {"username": "instagram", "biography": "test bio", "full_name": "", "source": "api"}
    with patch("app.routers.instagram._svc") as mock_svc:
        mock_svc.get_bio = AsyncMock(return_value=bio_data)
        r = client.get("/ig/bio?username=instagram")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "instagram"
    assert data["bio"] == "test bio"


# =============================================================================
# test_bios_endpoint: /username-bios?username=test → 200
# =============================================================================
def test_bios_endpoint():
    """/username-bios → 200, results listesi döner."""
    stub = {"platform": "GitHub", "url": "", "status": "exists", "display_name": "Test", "bio": "bio"}
    with patch.dict("app.routers.bios.FETCHERS", {
        "instagram": AsyncMock(return_value=stub),
        "github":    AsyncMock(return_value=stub),
        "reddit":    AsyncMock(return_value=stub),
        "x":         MagicMock(return_value=stub),
        "youtube":   AsyncMock(return_value=stub),
    }, clear=True):
        r = client.get("/username-bios?username=test")
    assert r.status_code == 200
    data = r.json()
    assert data["username"] == "test"
    assert isinstance(data["results"], list)
    assert len(data["results"]) == 5
