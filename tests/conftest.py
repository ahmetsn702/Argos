# tests/conftest.py
"""Shared pytest fixtures for the test suite."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from app.main import app

# Disable rate limiting globally for the test suite.
# slowapi exposes `enabled` on the Limiter instance attached to app.state.
if hasattr(app.state, "limiter"):
    app.state.limiter.enabled = False


@pytest.fixture(scope="session")
def client() -> TestClient:
    """A reusable FastAPI TestClient bound to the app under test."""
    return TestClient(app)


@pytest.fixture
def bio_payload():
    """A canonical /username-bios fetcher payload."""
    return {
        "platform": "Instagram",
        "url": "https://instagram.com/test",
        "status": "exists",
        "display_name": "Test User",
        "bio": "test bio",
    }
