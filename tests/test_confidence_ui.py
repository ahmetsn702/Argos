# tests/test_confidence_ui.py
"""Tests verifying confidence panel is injected into the correct UI files."""

from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)


def test_correlation_html_has_confidence_panel():
    resp = client.get("/stitch/correlation.html")
    assert resp.status_code == 200
    assert b"confidence-panel" in resp.content


def test_profile_html_has_confidence_bar():
    resp = client.get("/stitch/profile.html")
    assert resp.status_code == 200
    assert b"confidence-bar" in resp.content


def test_report_html_no_confidence():
    resp = client.get("/stitch/report.html")
    if resp.status_code == 200:
        assert b"confidence-panel" not in resp.content


def test_dashboard_html_no_confidence():
    resp = client.get("/stitch/dashboard.html")
    if resp.status_code == 200:
        assert b"confidence-panel" not in resp.content
