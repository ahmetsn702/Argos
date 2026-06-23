import pytest
from fastapi.testclient import TestClient
from app.main import app

client = TestClient(app)

def test_ping():
    r = client.get("/__ping")
    assert r.status_code == 200
    assert r.json()["ok"] is True

def test_routes_exist():
    r = client.get("/__routes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)

def test_username_scan():
    r = client.get("/username-scan?username=testuser")
    assert r.status_code == 200

def test_ig_bio():
    r = client.get("/ig/bio?username=instagram")
    assert r.status_code == 200

def test_combined_search():
    r = client.post("/combined-search?name=test")
    assert r.status_code == 200

def test_geo_health():
    r = client.get("/geo/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"

def test_scan_full_no_input():
    r = client.get("/scan/full")
    assert r.status_code == 400

def test_scan_full_with_email():
    r = client.get("/scan/full?email=test@example.com")
    assert r.status_code in [200, 206, 500]

def test_mosint_full():
    r = client.get("/mosint/full?email=test@example.com")
    assert r.status_code == 200

def test_mini_panel():
    r = client.get("/mini")
    assert r.status_code == 200


def test_phone_lookup_invalid():
    r = client.get("/phone/lookup?number=123")
    assert r.status_code == 400

def test_phone_lookup_valid():
    r = client.get("/phone/lookup?number=%2B905001234567")
    assert r.status_code == 200
    data = r.json()
    assert "normalized" in data
    assert "numverify" in data


def test_darkweb_lookup_invalid():
    r = client.get("/darkweb/lookup?query=ab")
    assert r.status_code == 400

def test_darkweb_lookup_valid():
    r = client.get("/darkweb/lookup?query=test@example.com")
    assert r.status_code == 200
    data = r.json()
    assert "query" in data
    assert "leakcheck" in data
    assert "summary" in data


def test_domain_lookup_invalid():
    r = client.get("/domain/lookup?target=ab")
    assert r.status_code == 400

def test_domain_lookup_valid():
    r = client.get("/domain/lookup?target=google.com")
    assert r.status_code == 200
    data = r.json()
    assert "ip" in data
    assert "dns" in data
    assert "shodan" in data
