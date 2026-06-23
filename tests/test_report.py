# tests/test_report.py
"""Tests for /report/generate endpoint (app.routers.report)."""
from unittest.mock import patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_FAKE_PDF = b"%PDF-1.4\n%fake\n"


def _async_return(value):
    async def _coro(*args, **kwargs):
        return value
    return _coro


def test_report_generate_with_email_returns_pdf():
    """email present → 200 + application/pdf body + attachment header."""
    with patch(
        "app.routers.report.generate_osint_report",
        side_effect=_async_return(_FAKE_PDF),
    ):
        r = client.post("/report/generate?email=user@example.com")
    assert r.status_code == 200
    assert r.headers["content-type"] == "application/pdf"
    assert "attachment" in r.headers.get("content-disposition", "")
    assert "footprint_user_example_com.pdf" in r.headers["content-disposition"]
    assert r.content.startswith(b"%PDF")


def test_report_generate_with_username_returns_pdf():
    """username present → 200 + correct filename slug."""
    with patch(
        "app.routers.report.generate_osint_report",
        side_effect=_async_return(_FAKE_PDF),
    ):
        r = client.post("/report/generate?username=alice")
    assert r.status_code == 200
    assert "footprint_alice.pdf" in r.headers["content-disposition"]


def test_report_generate_no_input_returns_400():
    """All of email/username/phone missing → 400 with detail."""
    r = client.post("/report/generate")
    assert r.status_code == 400
    detail = r.json().get("detail", "")
    assert "email" in detail or "username" in detail or "phone" in detail


def test_report_generate_service_error_propagates_as_500():
    """If the report builder explodes, FastAPI surfaces a 500 — but never silent success."""
    async def _boom(*args, **kwargs):
        raise RuntimeError("PDF backend offline")

    # raise_server_exceptions=False so we observe the HTTP-level 500 instead
    # of the raw RuntimeError bubbling up to pytest.
    safe_client = TestClient(app, raise_server_exceptions=False)
    with patch("app.routers.report.generate_osint_report", side_effect=_boom):
        r = safe_client.post("/report/generate?email=u@x.com")
    # The endpoint does not catch, so the exception becomes a 500.
    # The contract is: it must NOT silently return a corrupt PDF.
    assert r.status_code in (500, 502, 503)


def test_report_generate_invalid_timeout_returns_422():
    """timeout outside [5,60] → 422 from FastAPI Query validator."""
    r = client.post("/report/generate?email=u@x.com&timeout=1000")
    assert r.status_code == 422
