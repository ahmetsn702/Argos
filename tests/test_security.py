# tests/test_security.py
"""CORS ve temel güvenlik testleri."""
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_cors_headers():
    """OPTIONS /__ping with allowed origin → Access-Control-Allow-Origin present."""
    r = client.options(
        "/__ping",
        headers={
            "Origin": "http://localhost:8000",
            "Access-Control-Request-Method": "GET",
        },
    )
    # 200 veya 204 bekleniyor
    assert r.status_code in (200, 204)
    assert "access-control-allow-origin" in r.headers


def test_cors_disallowed_origin():
    """OPTIONS with disallowed origin → evil.com NOT in allow-origin header."""
    r = client.options(
        "/__ping",
        headers={
            "Origin": "http://evil.com",
            "Access-Control-Request-Method": "GET",
        },
    )
    allow_origin = r.headers.get("access-control-allow-origin", "")
    assert "evil.com" not in allow_origin


def test_ping_still_works():
    """GET /__ping → 200, ok:true (CORS sonrası normal endpoint bozulmadı)."""
    r = client.get("/__ping")
    assert r.status_code == 200
    assert r.json().get("ok") is True
