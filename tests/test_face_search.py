import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, AsyncMock, MagicMock
from app.main import app
from PIL import Image
import io
from app.services.face_service import _search_saucenao
from app.core.config import settings

client = TestClient(app)


def _make_test_jpeg() -> bytes:
    img = Image.new("RGB", (200, 200), color="blue")
    buf = io.BytesIO()
    img.save(buf, format="JPEG")
    return buf.getvalue()


def test_face_health():
    resp = client.get("/face/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] == "ok"
    assert "engines" in data
    assert "saucenao" in data["engines"]


def test_face_health_saucenao_state():
    with patch("app.core.config.settings.SAUCENAO_API_KEY", "fake_key"):
        resp = client.get("/face/health")
        assert resp.status_code == 200
        assert resp.json()["engines"]["saucenao"] is True

    with patch("app.core.config.settings.SAUCENAO_API_KEY", None):
        resp = client.get("/face/health")
        assert resp.status_code == 200
        assert resp.json()["engines"]["saucenao"] is False


@patch("app.services.face_service._search_saucenao")
@patch("app.services.face_service._search_google_vision")
def test_face_search_no_face(mock_gv, mock_sn):
    async def _sn_stub(*a, **kw):
        return {"engine": "saucenao", "ok": False, "results": [], "error": None, "took_ms": 100}

    async def _gv_stub(*a, **kw):
        return {"engine": "google_vision", "ok": False, "results": [], "error": "no_api_key", "took_ms": 0}

    mock_sn.side_effect = _sn_stub
    mock_gv.side_effect = _gv_stub

    jpeg = _make_test_jpeg()
    resp = client.post(
        "/face/search",
        files={"image": ("test.jpg", jpeg, "image/jpeg")},
        data={"engines": "saucenao,google_vision"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "verdict" in data
    assert "face_detection" in data
    assert "matches" in data


def test_face_search_invalid_content_type():
    resp = client.post(
        "/face/search",
        files={"image": ("test.txt", b"hello", "text/plain")},
        data={"engines": "yandex"},
    )
    assert resp.status_code == 400


@pytest.mark.anyio
async def test_search_saucenao_service_success():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "results": [
            {
                "header": {
                    "similarity": "92.5",
                    "index_name": "Pixiv Images"
                },
                "data": {
                    "ext_urls": ["https://www.pixiv.net/member_illust.php?mode=medium&illust_id=111"],
                    "title": "Anime Face"
                }
            }
        ]
    }

    # Patch settings.SAUCENAO_API_KEY
    with patch("app.services.face_service.settings.SAUCENAO_API_KEY", "dummy_key"):
        # Patch httpx.AsyncClient.post
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response) as mock_post:
            res = await _search_saucenao(b"fake_bytes")
            assert res["ok"] is True
            assert len(res["results"]) == 1
            assert res["results"][0]["url"] == "https://www.pixiv.net/member_illust.php?mode=medium&illust_id=111"
            assert res["results"][0]["similarity"] == 92.5
            assert res["results"][0]["title"] == "Anime Face"
            assert res["results"][0]["source"] == "Pixiv Images"


@pytest.mark.anyio
async def test_search_saucenao_service_no_key():
    with patch("app.services.face_service.settings.SAUCENAO_API_KEY", None):
        res = await _search_saucenao(b"fake_bytes")
        assert res["ok"] is False
        assert res["error"] == "no_api_key"


@pytest.mark.anyio
async def test_search_saucenao_service_http_error():
    mock_response = MagicMock()
    mock_response.status_code = 403
    mock_response.text = "Forbidden"

    with patch("app.services.face_service.settings.SAUCENAO_API_KEY", "dummy_key"):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            res = await _search_saucenao(b"fake_bytes")
            assert res["ok"] is False
            assert "HTTP 403" in res["error"]


@pytest.mark.anyio
async def test_search_saucenao_service_api_status_error():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "header": {
            "status": -1,
            "message": "The anonymous account type does not permit API usage."
        },
        "results": []
    }

    with patch("app.services.face_service.settings.SAUCENAO_API_KEY", "dummy_key"):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            res = await _search_saucenao(b"fake_bytes")
            assert res["ok"] is False
            assert "API Error -1" in res["error"]
            assert "anonymous account type" in res["error"]


@pytest.mark.anyio
async def test_search_saucenao_service_empty_results():
    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.json = lambda: {
        "header": {
            "status": 0,
            "message": "Success"
        },
        "results": []
    }

    with patch("app.services.face_service.settings.SAUCENAO_API_KEY", "dummy_key"):
        with patch("httpx.AsyncClient.post", new_callable=AsyncMock, return_value=mock_response):
            res = await _search_saucenao(b"fake_bytes")
            assert res["ok"] is True
            assert len(res["results"]) == 0
            assert res["error"] is None
