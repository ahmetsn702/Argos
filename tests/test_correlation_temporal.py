# tests/test_correlation_temporal.py
"""Tests for /correlation/timeline (Phase 3 of correlation engine)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# --- Helpers -----------------------------------------------------------------
def _hibp(breaches):
    return {"mosint": {"sources": {"hibp": {"ok": True, "data": {"breaches": breaches}}}}}


def _breach(name, date, classes=None):
    return {"Name": name, "BreachDate": date, "DataClasses": list(classes or [])}


# --- Tests -------------------------------------------------------------------
def test_timeline_empty_returns_empty_envelope():
    """Empty body → empty events, span=0, no clusters, no warnings."""
    r = client.post("/correlation/timeline", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["events"] == []
    assert data["span_years"] == 0.0
    assert data["breach_clusters"] == []
    assert data["password_reuse_warnings"] == []


def test_timeline_breach_events_sorted_by_date():
    """Three HIBP breaches → events sorted ascending by date."""
    payload = _hibp([
        _breach("LaterSite", "2022-06-15", ["Email addresses"]),
        _breach("EarlySite", "2018-01-10", ["Email addresses"]),
        _breach("MidSite", "2020-03-20", ["Email addresses"]),
    ])
    r = client.post("/correlation/timeline", json=payload)
    assert r.status_code == 200
    data = r.json()
    labels_by_date = [e["label"] for e in data["events"]]
    assert labels_by_date == ["EarlySite", "MidSite", "LaterSite"]
    assert all(e["event_type"] == "breach" for e in data["events"])
    assert all(e["source"] == "hibp" for e in data["events"])


def test_timeline_span_years_computed():
    """Two events 2 years apart → span_years ≈ 2.0."""
    payload = _hibp([
        _breach("A", "2020-01-01"),
        _breach("B", "2022-01-01"),
    ])
    r = client.post("/correlation/timeline", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert 1.99 <= data["span_years"] <= 2.01


def test_timeline_breach_cluster_detected_within_window():
    """3 breaches at 30-day intervals → one cluster of 3."""
    payload = _hibp([
        _breach("Site1", "2020-01-01"),
        _breach("Site2", "2020-01-31"),  # 30 days after
        _breach("Site3", "2020-03-01"),  # 30 days after Site2
    ])
    r = client.post("/correlation/timeline", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["breach_clusters"]) == 1
    cluster = data["breach_clusters"][0]
    assert cluster["count"] == 3
    assert cluster["breaches"] == ["Site1", "Site2", "Site3"]
    assert cluster["span_days"] == 60


def test_timeline_no_cluster_when_breaches_spread_out():
    """3 breaches with 200-day gaps → no cluster (each isolated)."""
    payload = _hibp([
        _breach("S1", "2020-01-01"),
        _breach("S2", "2020-07-20"),  # ~200 days gap
        _breach("S3", "2021-02-05"),
    ])
    r = client.post("/correlation/timeline", json=payload)
    assert r.status_code == 200
    assert r.json()["breach_clusters"] == []


def test_timeline_password_reuse_warning_format():
    """Passwords-class breach + bios with 2 platforms → warning contains
    breach name, date, AND platform list (strict format)."""
    payload = {
        **_hibp([_breach("Adobe2013", "2013-10-04", ["Passwords", "Email addresses"])]),
        "bios": {
            "results": [
                {"platform": "Instagram", "status": "exists"},
                {"platform": "X", "status": "exists"},
                {"platform": "Reddit", "status": "not_found"},
            ],
        },
    }
    r = client.post("/correlation/timeline", json=payload)
    assert r.status_code == 200
    warnings = r.json()["password_reuse_warnings"]
    assert len(warnings) == 1
    w = warnings[0]
    # Strict format markers
    assert "2013-10-04" in w
    assert "Adobe2013" in w
    assert "parola sınıfı" in w
    # Platform list (alphabetised by Pydantic-side `sorted()`)
    assert "Instagram" in w and "X" in w
    # not_found platform must NOT appear
    assert "Reddit" not in w


def test_timeline_password_warning_no_pattern_inference():
    """Ethical guard: warning text must not contain pattern/value/guess tokens."""
    payload = _hibp([_breach("Adobe2013", "2013-10-04", ["Passwords", "Password hashes"])])
    r = client.post("/correlation/timeline", json=payload)
    assert r.status_code == 200
    text = " ".join(r.json()["password_reuse_warnings"]).lower()
    forbidden = [
        "pattern", "tahmin", "olası parola", "yaygın parola",
        "parola tahmini", "password123", "common password",
        "format", "şifre tahmini",
    ]
    for f in forbidden:
        assert f not in text, f"Warning must not include '{f}'"


def test_timeline_domain_registration_event():
    """domain.whois.data.created_date → one domain_registered event."""
    payload = {
        "domain": {
            "whois": {
                "ok": True,
                "data": {"domain": "example.com", "created_date": "2010-05-15"},
            }
        }
    }
    r = client.post("/correlation/timeline", json=payload)
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) == 1
    e = events[0]
    assert e["event_type"] == "domain_registered"
    assert e["label"] == "example.com"
    assert e["source"] == "whois"
    assert e["date"].startswith("2010-05-15")


def test_timeline_extra_events_merged_and_sorted():
    """Caller-provided extra_events must merge with HIBP events and stay sorted."""
    payload = {
        **_hibp([_breach("Mid", "2020-06-01")]),
        "extra_events": [
            {"date": "2018-03-01", "event_type": "account_created",
             "label": "GitHub:alice", "source": "github"},
            {"date": "2022-12-01", "event_type": "account_created",
             "label": "Reddit:alice", "source": "reddit"},
            {"date": "not-a-date"},  # invalid → ignored
        ],
    }
    r = client.post("/correlation/timeline", json=payload)
    assert r.status_code == 200
    events = r.json()["events"]
    assert len(events) == 3  # invalid date dropped
    # Sorted ascending
    dates = [e["date"] for e in events]
    assert dates == sorted(dates)
    types = [e["event_type"] for e in events]
    assert types == ["account_created", "breach", "account_created"]
