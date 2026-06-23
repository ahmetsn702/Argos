# tests/test_correlation_graph.py
"""Tests for /correlation/graph (Phase 5 of correlation engine)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# --- Helpers -----------------------------------------------------------------
def _node_by_id(data, node_id):
    return next((n for n in data["nodes"] if n["id"] == node_id), None)


def _edges_between(data, a, b, edge_type=None):
    out = []
    for e in data["edges"]:
        match = ({e["from"], e["to"]} == {a, b})
        if edge_type:
            match = match and (e.get("edge_type") == edge_type)
        if match:
            out.append(e)
    return out


# --- Tests -------------------------------------------------------------------
def test_graph_empty_returns_empty_envelope():
    """Empty body → 0 nodes, 0 edges, expected metadata keys present."""
    r = client.post("/correlation/graph", json={})
    assert r.status_code == 200
    data = r.json()
    assert data["nodes"] == []
    assert data["edges"] == []
    assert data["metadata"]["node_count"] == 0
    assert data["metadata"]["edge_count"] == 0


def test_graph_email_with_breaches_creates_breached_in_edges():
    """mosint.email + 2 HIBP breaches → email node + 2 breach nodes + 2 edges."""
    payload = {
        "mosint": {
            "email": "alice@example.com",
            "verdict": "ok",
            "domain": "example.com",
            "sources": {
                "hibp": {
                    "ok": True,
                    "data": {
                        "breaches": [
                            {"Name": "Adobe2013", "BreachDate": "2013-10-04",
                             "DataClasses": ["Email addresses", "Passwords"]},
                            {"Name": "LinkedIn2012", "BreachDate": "2012-05-05",
                             "DataClasses": ["Email addresses"]},
                        ],
                    },
                }
            },
        },
    }
    r = client.post("/correlation/graph", json=payload)
    assert r.status_code == 200
    data = r.json()

    # Nodes
    assert _node_by_id(data, "email:alice@example.com") is not None
    assert _node_by_id(data, "breach:Adobe2013") is not None
    assert _node_by_id(data, "breach:LinkedIn2012") is not None
    assert _node_by_id(data, "domain:example.com") is not None

    # Email → breach edges
    e1 = _edges_between(data, "email:alice@example.com", "breach:Adobe2013", "breached_in")
    e2 = _edges_between(data, "email:alice@example.com", "breach:LinkedIn2012", "breached_in")
    assert len(e1) == 1 and len(e2) == 1

    # Email → domain (matching domain)
    e_reg = _edges_between(data, "email:alice@example.com", "domain:example.com", "registered")
    assert len(e_reg) == 1


def test_graph_profiles_from_bios_create_owns_edges():
    """person + bios with 2 exists profiles → person→profile edges."""
    payload = {
        "person": "Alice Smith",
        "bios": {
            "username": "alice92",
            "results": [
                {"platform": "Instagram", "status": "exists",
                 "display_name": "Alice", "url": "https://ig.com/alice92"},
                {"platform": "X", "status": "exists",
                 "display_name": "Alice", "url": "https://x.com/alice92"},
                {"platform": "Reddit", "status": "not_found"},
            ],
        },
    }
    r = client.post("/correlation/graph", json=payload)
    assert r.status_code == 200
    data = r.json()

    person_id = "person:Alice Smith"
    ig_id = "profile:instagram:alice92"
    x_id = "profile:x:alice92"

    assert _node_by_id(data, person_id) is not None
    assert _node_by_id(data, ig_id) is not None
    assert _node_by_id(data, x_id) is not None
    # not_found Reddit must NOT produce a node
    assert _node_by_id(data, "profile:reddit:alice92") is None

    assert len(_edges_between(data, person_id, ig_id, "owns")) == 1
    assert len(_edges_between(data, person_id, x_id, "owns")) == 1


def test_graph_identity_matches_create_same_as_edges():
    """identity_matches with verdict=likely_same → same_as edge between profiles."""
    payload = {
        "identity_matches": [
            {
                "entity_a": "profile:instagram:alice",
                "entity_b": "profile:x:alice_smith",
                "verdict": "likely_same",
                "confidence": 0.92,
            },
            {
                "entity_a": "profile:reddit:alice",
                "entity_b": "profile:github:bob",
                "verdict": "unlikely",  # → no edge expected
                "confidence": 0.2,
            },
        ],
    }
    r = client.post("/correlation/graph", json=payload)
    assert r.status_code == 200
    data = r.json()

    same_edges = [e for e in data["edges"] if e.get("edge_type") == "same_as"]
    assert len(same_edges) == 1
    assert same_edges[0]["from"] == "profile:instagram:alice"
    assert same_edges[0]["to"] == "profile:x:alice_smith"
    assert same_edges[0]["metadata"]["confidence"] == 0.92

    # The unlikely match must not produce reddit/github stub nodes
    assert _node_by_id(data, "profile:reddit:alice") is None
    assert _node_by_id(data, "profile:github:bob") is None


def test_graph_geo_cluster_creates_proximity_edges():
    """geo_cluster centroids with sources → geo_cluster nodes + geo_proximity edges."""
    payload = {
        "person": "Alice",
        "domain": {"target": "example.com", "ip": "1.2.3.4"},
        "geo_cluster": {
            "centroids": [
                {
                    "centroid_lat": 41.05,
                    "centroid_lng": 29.025,
                    "count": 2,
                    "sources": ["exif", "ip_geo"],
                },
            ],
        },
    }
    r = client.post("/correlation/graph", json=payload)
    assert r.status_code == 200
    data = r.json()

    cluster_id = "geo_cluster:0"
    assert _node_by_id(data, cluster_id) is not None
    # ip_geo source → cluster ↔ domain
    assert len(_edges_between(data, cluster_id, "domain:example.com", "geo_proximity")) == 1
    # exif source → cluster ↔ person
    assert len(_edges_between(data, cluster_id, "person:Alice", "geo_proximity")) == 1


def test_graph_vis_shape_uses_from_to_keys():
    """Edge dicts must use vis.js conventional `from`/`to` keys, not source/target."""
    payload = {
        "person": "Alice",
        "bios": {"username": "alice", "results": [{"platform": "X", "status": "exists"}]},
    }
    r = client.post("/correlation/graph", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert len(data["edges"]) == 1
    e = data["edges"][0]
    assert "from" in e and "to" in e
    assert "source" not in e and "target" not in e


def test_graph_centrality_normalised_by_max_degree():
    """A central node connected to N others has centrality 1.0; leaves have 1/N."""
    payload = {
        "person": "Alice",
        "mosint": {
            "email": "alice@example.com",
            "domain": "example.com",
            "sources": {
                "hibp": {
                    "ok": True,
                    "data": {
                        "breaches": [
                            {"Name": "B1", "DataClasses": []},
                            {"Name": "B2", "DataClasses": []},
                            {"Name": "B3", "DataClasses": []},
                        ],
                    },
                }
            },
        },
    }
    r = client.post("/correlation/graph", json=payload)
    assert r.status_code == 200
    data = r.json()
    centrality = data["metadata"]["centrality"]

    # email node touches: person(owns), 3 breaches(breached_in), domain(registered) = degree 5
    # leaves like B1/B2/B3 have degree 1
    email_c = centrality["email:alice@example.com"]
    leaf_c = centrality["breach:B1"]
    assert email_c == 1.0
    assert leaf_c == round(1 / 5, 4)


def test_graph_node_dedup_when_referenced_by_bios_and_identity():
    """Profile referenced both by bios AND identity_matches → only one node."""
    payload = {
        "bios": {
            "username": "alice",
            "results": [{"platform": "Instagram", "status": "exists",
                         "display_name": "Alice", "url": "https://ig.com/alice"}],
        },
        "identity_matches": [
            {
                "entity_a": "profile:instagram:alice",  # already created via bios
                "entity_b": "profile:x:alice_smith",     # synthesised stub
                "verdict": "likely_same",
                "confidence": 0.85,
            },
        ],
    }
    r = client.post("/correlation/graph", json=payload)
    assert r.status_code == 200
    data = r.json()
    ig_nodes = [n for n in data["nodes"] if n["id"] == "profile:instagram:alice"]
    assert len(ig_nodes) == 1  # dedup
    # x stub created from identity_match
    assert _node_by_id(data, "profile:x:alice_smith") is not None


def test_graph_metadata_reports_node_types_present():
    """metadata.node_types_present is a sorted unique list of node groups."""
    payload = {
        "person": "Alice",
        "mosint": {"email": "a@b.com", "sources": {"hibp": {"ok": True, "data": {"breaches": [
            {"Name": "X", "DataClasses": []}
        ]}}}},
        "domain": {"target": "b.com", "ip": "1.1.1.1"},
    }
    r = client.post("/correlation/graph", json=payload)
    assert r.status_code == 200
    types = r.json()["metadata"]["node_types_present"]
    assert types == sorted(set(types))
    assert {"person", "email", "breach", "domain", "ip"}.issubset(types)
