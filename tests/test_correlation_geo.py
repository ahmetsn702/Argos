# tests/test_correlation_geo.py
"""Tests for /correlation/geo (Phase 4 of correlation engine).

Cell math (default cell_size_deg=0.5°):
    Istanbul (41.0, 29.0)   → cell (82, 58)
    Istanbul (41.1, 29.05)  → cell (82, 58)   same
    Berlin   (52.55, 13.4)  → cell (105, 26)
    Berlin   (52.6, 13.45)  → cell (105, 26)  same
"""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# --- Helpers -----------------------------------------------------------------
def _domain(lat, lng, city="Istanbul", country="Turkey"):
    return {"geo": {"ok": True, "lat": lat, "lng": lng, "city": city, "country": country}}


def _exif(lat, lng, country="Turkey", region="Marmara", confidence=0.95):
    return {"lat": lat, "lng": lng, "country": country, "region": region, "confidence": confidence}


def _phone(lat, lng, location="Istanbul"):
    return {"numverify": {"location": location}, "geo": {"lat": lat, "lng": lng}}


# --- Tests -------------------------------------------------------------------
def test_geo_empty_returns_empty_envelope():
    """Empty body → no points, no centroids, primary_region=None."""
    r = client.post("/correlation/geo", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["points"] == []
    assert data["centroids"] == []
    assert data["primary_region"] is None


def test_geo_single_point_no_cluster_but_primary_set():
    """One IP geo point alone → 1 point, 0 clusters, primary_region from point label."""
    r = client.post("/correlation/geo", json={"domain": _domain(41.0, 29.0)})
    assert r.status_code == 200
    data = r.json()
    assert len(data["points"]) == 1
    assert data["points"][0]["source"] == "ip_geo"
    assert data["centroids"] == []
    # No clusters → fall back to highest-confidence point's label
    assert data["primary_region"] == "Istanbul, Turkey"


def test_geo_two_points_same_cell_form_cluster():
    """IP geo + EXIF in same Istanbul cell → 1 cluster of 2 with both sources."""
    payload = {
        "domain": _domain(41.0, 29.0, city="Istanbul"),
        "exif": _exif(41.1, 29.05, region="Istanbul"),
    }
    r = client.post("/correlation/geo", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["points"]) == 2
    assert len(data["centroids"]) == 1
    cluster = data["centroids"][0]
    assert cluster["count"] == 2
    assert cluster["sources"] == ["exif", "ip_geo"]
    # Centroid is the mean
    assert abs(cluster["centroid_lat"] - 41.05) < 1e-6
    assert abs(cluster["centroid_lng"] - 29.025) < 1e-6


def test_geo_two_points_different_cells_no_cluster():
    """Istanbul + Berlin → 2 points, 0 clusters."""
    payload = {
        "domain": _domain(41.0, 29.0, city="Istanbul"),
        "exif": _exif(52.55, 13.4, region="Berlin"),
    }
    r = client.post("/correlation/geo", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["points"]) == 2
    assert data["centroids"] == []


def test_geo_two_clusters_sorted_by_count():
    """3 points in Istanbul cell + 2 in Berlin cell → bigger cluster first."""
    payload = {
        "domain": _domain(41.0, 29.0, city="Istanbul"),
        "exif": _exif(41.1, 29.05, region="Istanbul"),
        "extra_points": [
            {"lat": 41.05, "lng": 29.0, "source": "checkin", "label": "Istanbul"},
            {"lat": 52.55, "lng": 13.4, "source": "checkin", "label": "Berlin"},
            {"lat": 52.6, "lng": 13.45, "source": "checkin", "label": "Berlin"},
        ],
    }
    r = client.post("/correlation/geo", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["points"]) == 5
    assert len(data["centroids"]) == 2
    assert data["centroids"][0]["count"] == 3  # Istanbul first
    assert data["centroids"][1]["count"] == 2  # Berlin second
    # Primary region from top cluster label list
    assert data["primary_region"] in ("Istanbul, Turkey", "Istanbul")


def test_geo_phone_with_caller_supplied_coords():
    """phone.geo.lat/lng → point with source='phone' appears."""
    payload = {"phone": _phone(41.01, 28.97, location="Istanbul")}
    r = client.post("/correlation/geo", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["points"]) == 1
    assert data["points"][0]["source"] == "phone"
    assert data["points"][0]["label"] == "Istanbul"


def test_geo_extra_points_supported():
    """`extra_points` flow merges into the points list."""
    payload = {
        "extra_points": [
            {"lat": 39.9, "lng": 32.85, "source": "checkin", "label": "Ankara", "confidence": 0.7},
            {"lat": 38.41, "lng": 27.14, "source": "checkin", "label": "Izmir"},
        ],
    }
    r = client.post("/correlation/geo", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["points"]) == 2
    sources = {p["source"] for p in data["points"]}
    assert sources == {"checkin"}
    labels = {p["label"] for p in data["points"]}
    assert labels == {"Ankara", "Izmir"}


def test_geo_invalid_coords_rejected():
    """Out-of-range / non-numeric coords are silently dropped."""
    payload = {
        "domain": {"geo": {"lat": 200.0, "lng": 0.0}},  # lat > 90
        "exif": {"lat": "not-a-number", "lng": 29.0},
        "extra_points": [
            {"lat": None, "lng": 29.0},
            {"lat": 41.0, "lng": 200.0},  # lng > 180
            {"lat": True, "lng": 29.0},   # bool excluded
            {"lat": 41.0, "lng": 29.0, "source": "ok"},  # valid
        ],
    }
    r = client.post("/correlation/geo", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["points"]) == 1  # only the valid extra_point
    assert data["points"][0]["source"] == "ok"


def test_geo_custom_cell_size_changes_clustering():
    """Larger cell merges previously-separate cells; smaller splits."""
    payload_base = {
        "domain": _domain(41.0, 29.0),
        "exif": _exif(41.4, 29.4),  # in same cell with default 0.5°
    }
    # default 0.5° → both points cell (82, 58) → 1 cluster
    r1 = client.post("/correlation/geo", json=payload_base)
    assert len(r1.json()["centroids"]) == 1

    # cell_size_deg = 0.1 → (410, 290) vs (414, 294) → different cells → 0 clusters
    payload_small = {**payload_base, "cell_size_deg": 0.1}
    r2 = client.post("/correlation/geo", json=payload_small)
    assert len(r2.json()["centroids"]) == 0
    assert len(r2.json()["points"]) == 2


def test_geo_cell_size_validation():
    """cell_size_deg must be > 0 and <= 10. Pydantic enforces."""
    r = client.post("/correlation/geo", json={"cell_size_deg": 0})
    assert r.status_code == 422
    r = client.post("/correlation/geo", json={"cell_size_deg": 50})
    assert r.status_code == 422
    r = client.post("/correlation/geo", json={"cell_size_deg": -1})
    assert r.status_code == 422
