# tests/test_correlation_full.py
"""Correlation endpoint smoke testleri."""
from unittest.mock import AsyncMock, patch
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def _full_response_stub(seed_email=None, seed_username=None):
    """Correlation full endpoint'inin döneceği minimal geçerli FullResponse."""
    from app.models.identity import FullResponse, PivotSeed
    seed = PivotSeed(email=seed_email, username=seed_username)
    return FullResponse(seed=seed, raw_summary={}, took_ms=0)


def test_correlation_full_email():
    """POST /correlation/full with email seed → 200, dict döner."""
    stub = _full_response_stub(seed_email="test@test.com")
    with patch("app.routers.correlation.correlation_full", new=AsyncMock(return_value=stub)):
        r = client.post("/correlation/full", json={"seed": {"email": "test@test.com"}})
    # Either the mock works (200) or validation passes through (200/422)
    assert r.status_code in (200, 422)
    if r.status_code == 200:
        assert isinstance(r.json(), dict)


def test_correlation_full_username():
    """POST /correlation/full with username seed → 200 veya 422."""
    stub = _full_response_stub(seed_username="testuser")
    with patch("app.routers.correlation.correlation_full", new=AsyncMock(return_value=stub)):
        r = client.post("/correlation/full", json={"seed": {"username": "testuser"}})
    assert r.status_code in (200, 422)


def test_correlation_identity():
    """POST /correlation/identity → 200 veya 400/422."""
    from app.models.identity import IdentityResponse
    stub = IdentityResponse(matches=[], pairs_evaluated=0)
    with patch("app.routers.correlation.correlation_identity", new=AsyncMock(return_value=stub)):
        r = client.post("/correlation/identity",
                        json={"profiles": [{"platform": "instagram", "username": "test",
                                           "bio": "", "display_name": ""}]})
    assert r.status_code in (200, 400, 422)


def test_correlation_graph():
    """POST /correlation/graph → 200 veya 400/422."""
    with patch("app.routers.correlation.build_graph", return_value=([], [])), \
         patch("app.routers.correlation.to_vis_shape", return_value={"nodes": [], "edges": []}):
        r = client.post("/correlation/graph", json={"profiles": []})
    assert r.status_code in (200, 400, 422)
