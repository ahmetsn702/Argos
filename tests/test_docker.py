# tests/test_docker.py
"""Smoke tests for the deployment surface used by the Docker healthcheck and
the docker_start scripts.

These hit the FastAPI app directly via TestClient (no real Docker engine
required) so they validate the *contract* — that the endpoints exist and
return the expected shape — independently of containerisation.
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_ping_returns_ok():
    """`/__ping` is the endpoint baked into the Dockerfile HEALTHCHECK and the
    docker-compose healthcheck. It MUST return JSON containing `ok: true`."""
    r = client.get("/__ping")
    assert r.status_code == 200
    data = r.json()
    assert data.get("ok") is True
    # Service identifier is also part of the documented contract.
    assert data.get("service") == "argos"
    assert data.get("version") == "4.0"


def test_routes_endpoint():
    """`/__routes` lists all registered routes for diagnostic purposes — it
    must return a non-empty list of {path, name} dicts."""
    r = client.get("/__routes")
    assert r.status_code == 200
    routes = r.json()
    assert isinstance(routes, list)
    assert len(routes) > 0

    # Every entry has the documented shape.
    for entry in routes[:5]:
        assert isinstance(entry, dict)
        assert "path" in entry
        assert "name" in entry

    # The healthcheck endpoint itself must be in the list.
    paths = {entry["path"] for entry in routes}
    assert "/__ping" in paths


def test_static_ui_served():
    """Static UI must be served from the `/ui` mount so the post-deploy
    smoke check (`docker_start.{sh,ps1}` printing the dashboard URL) is
    actually reachable."""
    r = client.get("/ui/dashboard.html")
    assert r.status_code == 200
    ct = r.headers.get("content-type", "").lower()
    assert "html" in ct
    # Page identifies itself so we know we got real content, not an error
    # page rendered as HTML.
    assert "ARGOS" in r.text
