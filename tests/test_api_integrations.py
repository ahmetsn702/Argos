# tests/test_api_integrations.py
import pytest
import httpx
from unittest.mock import AsyncMock, patch, MagicMock
from app.services.darkweb_service import _search_breachdirectory, darkweb_osint
from app.services.phone_service import veriphone_lookup, phone_osint
from app.services.face_service import _search_tineye


@pytest.mark.anyio
async def test_search_breachdirectory_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "found": 1,
        "result": [
            {
                "password": "pass123",
                "sha1": "sha1hash",
                "sources": "BreachOne, BreachTwo"
            }
        ]
    }

    with patch("app.services.darkweb_service.settings.RAPIDAPI_KEY", "fake_key"):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response) as mock_get:
            res = await _search_breachdirectory("test@example.com")
            assert res["ok"] is True
            assert res["found"] == 1
            assert len(res["sources"]) == 2
            assert res["sources"][0]["name"] == "BreachOne"


@pytest.mark.anyio
async def test_search_breachdirectory_no_key():
    with patch("app.services.darkweb_service.settings.RAPIDAPI_KEY", None):
        res = await _search_breachdirectory("test@example.com")
        assert res["ok"] is False
        assert "RAPIDAPI_KEY eksik" in res["error"]


@pytest.mark.anyio
async def test_veriphone_lookup_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "status": "success",
        "phone": "+905001234567",
        "phone_valid": True,
        "phone_type": "mobile",
        "phone_region": "Istanbul",
        "country": "Turkey",
        "country_code": "TR",
        "country_prefix": "90",
        "international_number": "+90 500 123 45 67",
        "local_number": "0500 123 45 67",
        "e164": "+905001234567",
        "carrier": "Turkcell"
    }

    with patch("app.services.phone_service.settings.VERIPHONE_KEY", "fake_key"):
        with patch("httpx.AsyncClient.get", new_callable=AsyncMock, return_value=mock_response):
            res = await veriphone_lookup("+905001234567")
            assert res["ok"] is True
            assert res["valid"] is True
            assert res["carrier"] == "Turkcell"
            assert res["line_type"] == "mobile"
            assert res["location"] == "Istanbul"


@pytest.mark.anyio
async def test_veriphone_lookup_no_key():
    with patch("app.services.phone_service.settings.VERIPHONE_KEY", None):
        res = await veriphone_lookup("+905001234567")
        assert res["ok"] is False
        assert "VERIPHONE_KEY eksik" in res["error"]


@pytest.mark.anyio
async def test_search_tineye_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "stats": {
            "total_results": 1
        },
        "results": [
            {
                "image_url": "https://match.com/img.jpg",
                "page_url": "https://match.com/page",
                "domain": "match.com",
                "score": 85.5,
                "backlinks": []
            }
        ]
    }

    with patch("app.services.face_service.settings.TINEYE_KEY", "fake_key"):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            res = await _search_tineye(b"fake_bytes")
            assert res["ok"] is True
            assert len(res["results"]) == 1
            assert res["results"][0]["url"] == "https://match.com/page"
            assert res["results"][0]["title"] == "match.com"
            assert res["results"][0]["score"] == 85.5


@pytest.mark.anyio
async def test_search_tineye_no_key():
    with patch("app.services.face_service.settings.TINEYE_KEY", None):
        res = await _search_tineye(b"fake_bytes")
        assert res["ok"] is False
        assert "no_api_key" in res["error"]


@pytest.mark.anyio
async def test_phone_osint_fallback_to_veriphone():
    # Mock numverify to fail, abstract to fail, and veriphone to succeed
    numverify_fail = {"ok": False, "error": "Numverify failed"}
    abstract_fail = {"ok": False, "error": "Abstract failed"}
    veriphone_success = {
        "ok": True,
        "valid": True,
        "number": "+90 500 123 45 67",
        "local": "0500 123 45 67",
        "country": "Turkey",
        "carrier": "Turkcell",
        "line_type": "mobile",
        "location": "Istanbul"
    }

    with patch("app.services.phone_service.numverify_lookup", new_callable=AsyncMock, return_value=numverify_fail), \
         patch("app.services.phone_service.abstract_phone_lookup", new_callable=AsyncMock, return_value=abstract_fail), \
         patch("app.services.phone_service.veriphone_lookup", new_callable=AsyncMock, return_value=veriphone_success):
        
        res = await phone_osint("+905001234567")
        assert res["numverify"]["ok"] is True
        assert res["numverify"]["valid"] is True
        assert res["numverify"]["carrier"] == "Turkcell"
        assert res["abstract"]["ok"] is False
