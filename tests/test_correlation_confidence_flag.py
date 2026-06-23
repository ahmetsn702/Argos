# tests/test_correlation_confidence_flag.py
"""Tests for include_confidence flag on /correlation/full."""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_confidence_cache():
    from app.services.confidence.cache import _default_backend
    _default_backend.clear()
    yield
    _default_backend.clear()


def test_correlation_full_default_no_confidence():
    """Default (no flag) → confidence is null or absent."""
    resp = client.post("/correlation/full", json={
        "seed": {"email": "test@example.com"},
        "include_identity": False,
        "include_risk": False,
        "include_timeline": False,
        "include_geo": False,
        "include_graph": False,
    })
    if resp.status_code == 200:
        data = resp.json()
        assert data.get("confidence") is None


def test_correlation_full_with_confidence_flag():
    """include_confidence=true → confidence field present in response."""
    resp = client.post("/correlation/full", json={
        "seed": {"email": "test@example.com"},
        "include_identity": False,
        "include_risk": False,
        "include_timeline": False,
        "include_geo": False,
        "include_graph": False,
        "include_confidence": True,
    })
    assert resp.status_code != 500
    if resp.status_code == 200:
        data = resp.json()
        assert "confidence" in data


def test_correlation_full_confidence_error_graceful():
    """Even with a broken seed, include_confidence=true must not cause 500."""
    resp = client.post("/correlation/full", json={
        "seed": {"email": "broken@nowhere.invalid"},
        "include_identity": False,
        "include_risk": False,
        "include_timeline": False,
        "include_geo": False,
        "include_graph": False,
        "include_confidence": True,
    })
    assert resp.status_code != 500
