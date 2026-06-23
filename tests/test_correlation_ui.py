# tests/test_correlation_ui.py
"""Smoke test: ui/correlation.html is served and contains the expected anchors.

The static-files mount in app/main.py exposes the `ui/` directory at /ui/,
so any HTML page placed there is reachable as /ui/<filename>.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_correlation_html_is_served():
    """GET /ui/correlation.html → 200 with HTML content type."""
    r = client.get("/ui/correlation.html")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "").lower()
    assert "html" in ct

    body = r.text
    # Page identifies itself
    assert "ARGOS // CORRELATION" in body
    # All 7 endpoints are wired up via the manual modules section + run-full
    assert "/correlation/identity" in body
    assert "/correlation/risk" in body
    assert "/correlation/timeline" in body
    assert "/correlation/geo" in body
    assert "/correlation/graph" in body
    assert "/correlation/pivot" in body
    assert "run-full" in body  # main full-analysis button id


def test_dashboard_links_to_correlation_page():
    """The dashboard sidebar should link to the new correlation page."""
    r = client.get("/ui/dashboard.html")
    assert r.status_code == 200
    body = r.text
    assert "/ui/correlation.html" in body
    # The pre-existing "Unified Analysis" button must not have been removed
    assert "Unified Analysis" in body


def test_graph_html_is_served():
    """GET /ui/graph.html → 200 and contains the vis-network CDN + 3 data tabs."""
    r = client.get("/ui/graph.html")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "").lower()
    assert "html" in ct

    body = r.text
    assert "ARGOS // GRAPH VIEW" in body
    # vis-network library is loaded from CDN
    assert "vis-network" in body
    # The 3 data source tabs are wired
    assert 'data-tab="auto"' in body
    assert 'data-tab="api"' in body
    assert 'data-tab="paste"' in body
    # API mode wires through the existing graph endpoint
    assert "/correlation/graph" in body
    # sessionStorage handoff key matches what correlation.html writes
    assert "correlation_graph" in body
