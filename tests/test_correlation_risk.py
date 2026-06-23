# tests/test_correlation_risk.py
"""Tests for /correlation/risk (Phase 2 of correlation engine)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# --- Helpers -----------------------------------------------------------------
def _hibp_payload(breaches):
    """Build a /mosint/full-shaped payload containing HIBP breaches."""
    return {
        "mosint": {
            "sources": {
                "hibp": {"ok": True, "data": {"breaches": breaches}},
            }
        }
    }


# --- Tests -------------------------------------------------------------------
def test_risk_low_when_no_signals():
    """Empty payload → score=0, band=low, no findings, no recommendations."""
    r = client.post("/correlation/risk", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["score"] == 0
    assert data["band"] == "low"
    assert data["findings"] == []
    assert data["recommendations"] == []


def test_risk_breach_only_no_sensitive_class():
    """1 HIBP breach with non-sensitive classes → breach_exposure only,
    no sensitive_data_leak, no password recommendation."""
    payload = _hibp_payload([
        {"Name": "ExampleSite", "BreachDate": "2020-01-01",
         "DataClasses": ["Email addresses", "Usernames"]},
    ])
    r = client.post("/correlation/risk", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["score"] > 0
    cats = {f["category"] for f in data["findings"]}
    assert "breach_exposure" in cats
    assert "sensitive_data_leak" not in cats
    # 2FA recommendation should fire on any breach
    assert any("2FA" in r for r in data["recommendations"])


def test_risk_passwords_leak_creates_sensitive_finding_and_advice():
    """Breach with Passwords class → sensitive_data_leak finding + name-only
    rotation advice. NO password pattern inference."""
    payload = _hibp_payload([
        {"Name": "Adobe2013", "BreachDate": "2013-10-04",
         "DataClasses": ["Email addresses", "Passwords", "Password hints"]},
    ])
    r = client.post("/correlation/risk", json=payload)
    assert r.status_code == 200
    data = r.json()
    cats = {f["category"] for f in data["findings"]}
    assert "sensitive_data_leak" in cats
    # Rotation advice mentions the breach name and the word "parol"
    rec_text = " ".join(data["recommendations"])
    assert "Adobe2013" in rec_text
    assert "parol" in rec_text.lower()


def test_risk_critical_with_all_signals():
    """All 5 categories triggered → score >= 75 → critical band."""
    breaches = [
        {"Name": f"Site{i}", "BreachDate": "2020-01-01",
         "DataClasses": (["Passwords", "Credit cards", "SSN"] if i < 3 else ["Email addresses"])}
        for i in range(12)
    ]
    payload = {
        "mosint": {
            "sources": {
                "hibp": {"ok": True, "data": {"breaches": breaches}},
                "emailrep": {"data": {
                    "suspicious": True,
                    "details": {"malicious_activity": True, "disposable": True},
                }},
            }
        },
        "bios": {
            "username": "alice",
            "results": [
                {"platform": f"P{i}", "status": "exists"} for i in range(7)
            ],
        },
        "phone": {"numverify": {"valid": True, "carrier": "Vodafone TR", "location": "Istanbul"}},
        "darkweb": {"summary": {"leak_count": 5}},
    }
    r = client.post("/correlation/risk", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["band"] == "critical"
    assert data["score"] >= 75
    # All 5 categories should be present
    cats = {f["category"] for f in data["findings"]}
    assert cats == {
        "breach_exposure",
        "sensitive_data_leak",
        "profile_sprawl",
        "email_reputation",
        "phone_exposure",
    }


def test_risk_profile_sprawl_weighted_correctly():
    """6 platforms with status=exists → profile_sprawl finding with weight=18."""
    payload = {
        "bios": {
            "username": "alice",
            "count": 7,
            "results": [
                {"platform": "Instagram", "status": "exists"},
                {"platform": "X", "status": "exists"},
                {"platform": "GitHub", "status": "exists"},
                {"platform": "Reddit", "status": "exists"},
                {"platform": "YouTube", "status": "exists"},
                {"platform": "TikTok", "status": "exists"},
                {"platform": "Threads", "status": "not_found"},
            ],
        }
    }
    r = client.post("/correlation/risk", json=payload)
    assert r.status_code == 200
    data = r.json()
    sprawl = next((f for f in data["findings"] if f["category"] == "profile_sprawl"), None)
    assert sprawl is not None
    assert sprawl["weight"] == 18  # 6 exists * 3
    rec_text = " ".join(data["recommendations"])
    assert "gizlilik" in rec_text.lower()


def test_risk_email_reputation_only():
    """emailrep.suspicious=true + malicious_activity=true → email_reputation finding."""
    payload = {
        "mosint": {
            "sources": {
                "emailrep": {
                    "data": {
                        "suspicious": True,
                        "details": {"malicious_activity": True},
                    }
                }
            }
        }
    }
    r = client.post("/correlation/risk", json=payload)
    assert r.status_code == 200
    data = r.json()
    cats = {f["category"] for f in data["findings"]}
    assert "email_reputation" in cats
    # Should NOT trigger breach finding (no breaches in payload)
    assert "breach_exposure" not in cats


def test_risk_no_password_pattern_inference():
    """Ethical guard: even with passwords leaked, recommendations must NOT
    include password content, format, or guessing instructions."""
    payload = _hibp_payload([
        {"Name": "Adobe2013", "BreachDate": "2013-10-04",
         "DataClasses": ["Passwords", "Password hashes", "Password hints"]},
    ])
    r = client.post("/correlation/risk", json=payload)
    assert r.status_code == 200
    data = r.json()
    rec_text = " ".join(data["recommendations"]).lower()
    # Forbidden tokens that would indicate pattern inference / value leakage
    forbidden = [
        "pattern", "tahmin",
        "example password", "common password", "password123",
        "yaygın parola", "olası parola", "parola tahmini",
    ]
    for f in forbidden:
        assert f not in rec_text, f"Recommendation must not include '{f}'"


def test_risk_band_thresholds():
    """Verify band boundaries: medium (>=25), high (>=50), critical (>=75)."""
    # 4 breaches, no sensitive = score 30 → high (>=25, <50 → medium actually)
    # Let me build a precise medium-band case
    payload_medium = _hibp_payload([
        {"Name": f"Site{i}", "BreachDate": "2020-01-01", "DataClasses": ["Email"]}
        for i in range(2)  # 2 breaches → score 20 → low (<25)
    ])
    r = client.post("/correlation/risk", json=payload_medium)
    assert r.json()["score"] == 20
    assert r.json()["band"] == "low"

    # 4 breaches → score 30 → medium
    payload_med2 = _hibp_payload([
        {"Name": f"Site{i}", "BreachDate": "2020-01-01", "DataClasses": ["Email"]}
        for i in range(4)
    ])
    r2 = client.post("/correlation/risk", json=payload_med2)
    assert r2.json()["score"] == 30
    assert r2.json()["band"] == "medium"
