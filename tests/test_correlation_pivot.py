# tests/test_correlation_pivot.py
"""Tests for /correlation/pivot (Phase 6 of correlation engine).

Mocks `app.services.correlation.pivot_engine._call_mosint` and `_call_bios`
(both async wrappers around the underlying OSINT endpoints) so no real
network traffic occurs during tests.
"""
from unittest.mock import AsyncMock, patch

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# --- Helpers -----------------------------------------------------------------
def _mosint_payload(email, domain="example.com", breach_names=()):
    return {
        "email": email,
        "domain": domain,
        "syntax_ok": True,
        "verdict": "ok",
        "sources": {
            "hibp": {
                "ok": True,
                "data": {"breaches": [{"Name": n, "DataClasses": []} for n in breach_names]},
            }
        },
    }


def _bios_payload(platform_bios):
    """platform_bios = {"Instagram": "bio text", "X": "...", ...}"""
    return [
        {
            "platform": p,
            "url": f"https://{p.lower()}.com/?",
            "status": "exists",
            "display_name": "Stub",
            "bio": b,
        }
        for p, b in platform_bios.items()
    ]


# --- Tests -------------------------------------------------------------------
def test_pivot_empty_seed_returns_empty_result():
    """No seed → no entities, no expansion, depth_reached=0, graph has only the anchor."""
    r = client.post("/correlation/pivot", json={"seed": {}})
    assert r.status_code == 200
    data = r.json()
    assert data["discovered"] == []
    assert data["depth_reached"] == 0
    assert data["truncated"] is False
    # graph included by default; only the synthetic anchor node
    assert data["graph"] is not None
    assert len(data["graph"]["nodes"]) == 1


def test_pivot_email_seed_extracts_breaches_and_domain():
    """Seed email with mocked mosint → email + breach + domain entities discovered."""
    with patch(
        "app.services.correlation.pivot_engine._call_mosint",
        new_callable=AsyncMock,
    ) as m_mosint, patch(
        "app.services.correlation.pivot_engine._call_bios",
        new_callable=AsyncMock,
    ) as m_bios:
        m_mosint.return_value = _mosint_payload(
            "alice@example.com", breach_names=["Adobe2013"],
        )
        m_bios.return_value = []  # username derivation returns no profiles

        r = client.post(
            "/correlation/pivot",
            json={"seed": {"email": "alice@example.com"}, "max_depth": 1},
        )
    assert r.status_code == 200
    data = r.json()

    # Mosint called for the seed email
    m_mosint.assert_awaited()
    types = {d["type"] for d in data["discovered"]}
    assert "email" in types
    assert "breach" in types
    assert "domain" in types
    assert data["depth_reached"] == 1


def test_pivot_username_seed_extracts_profiles_and_bio_emails():
    """Seed username: bios returns 2 profiles with bio mentioning a new email."""
    with patch(
        "app.services.correlation.pivot_engine._call_bios",
        new_callable=AsyncMock,
    ) as m_bios, patch(
        "app.services.correlation.pivot_engine._call_mosint",
        new_callable=AsyncMock,
    ) as m_mosint:
        m_bios.return_value = _bios_payload({
            "Instagram": "Contact: bob@example.com 📩",
            "X": "no contact info",
        })
        m_mosint.return_value = _mosint_payload("bob@example.com")

        r = client.post(
            "/correlation/pivot",
            json={"seed": {"username": "alice"}, "max_depth": 2},
        )
    assert r.status_code == 200
    data = r.json()

    discovered_values = [(d["type"], d["value"]) for d in data["discovered"]]
    # 2 profiles created from bios
    assert ("profile", "alice") in discovered_values
    # bio email surfaced
    assert ("email", "bob@example.com") in discovered_values


def test_pivot_depth_2_chains_through_extracted_email():
    """Username → profile bio mentions email → email expanded → its domain discovered."""
    bios_responses = {
        "alice": _bios_payload({"Instagram": "📩 carol@acme.io"}),
        # If pivot derives "carol" as a username candidate, bios may be called for it too.
        "carol": [],
    }

    async def bios_side_effect(username):
        return bios_responses.get(username, [])

    with patch(
        "app.services.correlation.pivot_engine._call_bios",
        new_callable=AsyncMock,
        side_effect=bios_side_effect,
    ), patch(
        "app.services.correlation.pivot_engine._call_mosint",
        new_callable=AsyncMock,
    ) as m_mosint:
        m_mosint.return_value = _mosint_payload("carol@acme.io", domain="acme.io")

        r = client.post(
            "/correlation/pivot",
            json={"seed": {"username": "alice"}, "max_depth": 2},
        )
    assert r.status_code == 200
    data = r.json()

    pairs = [(d["type"], d["value"]) for d in data["discovered"]]
    # Round 1 (expand "alice" username): profile + email surfaced
    assert ("email", "carol@acme.io") in pairs
    # Round 2 (expand "carol@acme.io" email): domain "acme.io" added
    assert ("domain", "acme.io") in pairs
    assert data["depth_reached"] == 2


def test_pivot_loop_protection_via_seen_set():
    """If two profile bios both mention the same email, it's added once only."""
    with patch(
        "app.services.correlation.pivot_engine._call_bios",
        new_callable=AsyncMock,
    ) as m_bios, patch(
        "app.services.correlation.pivot_engine._call_mosint",
        new_callable=AsyncMock,
    ) as m_mosint:
        m_bios.return_value = _bios_payload({
            "Instagram": "x@y.com",
            "X": "x@y.com again",
            "GitHub": "still x@y.com",
        })
        m_mosint.return_value = _mosint_payload("x@y.com")

        r = client.post(
            "/correlation/pivot",
            json={"seed": {"username": "alice"}, "max_depth": 2},
        )
    assert r.status_code == 200
    data = r.json()

    email_entries = [d for d in data["discovered"] if d["type"] == "email" and d["value"] == "x@y.com"]
    assert len(email_entries) == 1  # deduped via seen-set


def test_pivot_max_entities_per_level_truncates():
    """`max_entities_per_level=1` → only one new entity per round → truncated=True."""
    with patch(
        "app.services.correlation.pivot_engine._call_bios",
        new_callable=AsyncMock,
    ) as m_bios, patch(
        "app.services.correlation.pivot_engine._call_mosint",
        new_callable=AsyncMock,
    ) as m_mosint:
        # bios returns 5 profiles → 5 new entities at depth 1, but cap=1
        m_bios.return_value = _bios_payload({
            "Instagram": "", "X": "", "GitHub": "", "Reddit": "", "YouTube": "",
        })
        m_mosint.return_value = _mosint_payload("alice@example.com")

        r = client.post(
            "/correlation/pivot",
            json={
                "seed": {"username": "alice"},
                "max_depth": 1,
                "max_entities_per_level": 1,
            },
        )
    assert r.status_code == 200
    data = r.json()
    profile_count = sum(1 for d in data["discovered"] if d["type"] == "profile")
    # At least the cap was applied; we expect strictly fewer than 5 profiles
    assert profile_count <= 1
    assert data["truncated"] is True


def test_pivot_max_depth_validation():
    """max_depth must be in [1, 3]; 0 and 4 → 422."""
    base = {"seed": {"email": "a@b.com"}}
    assert client.post("/correlation/pivot", json={**base, "max_depth": 0}).status_code == 422
    assert client.post("/correlation/pivot", json={**base, "max_depth": 4}).status_code == 422
    assert client.post("/correlation/pivot", json={**base, "max_depth": -1}).status_code == 422


def test_pivot_time_budget_validation():
    """time_budget_seconds must be > 0 and ≤ 180."""
    base = {"seed": {"email": "a@b.com"}}
    assert client.post("/correlation/pivot", json={**base, "time_budget_seconds": 0}).status_code == 422
    assert client.post("/correlation/pivot", json={**base, "time_budget_seconds": 200}).status_code == 422


def test_pivot_includes_graph_when_requested_and_omits_when_not():
    """`include_graph` toggles the `graph` field in the response."""
    with patch(
        "app.services.correlation.pivot_engine._call_mosint",
        new_callable=AsyncMock,
    ) as m_mosint, patch(
        "app.services.correlation.pivot_engine._call_bios",
        new_callable=AsyncMock,
    ) as m_bios:
        m_mosint.return_value = _mosint_payload("alice@example.com")
        m_bios.return_value = []

        r1 = client.post(
            "/correlation/pivot",
            json={"seed": {"email": "alice@example.com"}, "max_depth": 1, "include_graph": True},
        )
        r2 = client.post(
            "/correlation/pivot",
            json={"seed": {"email": "alice@example.com"}, "max_depth": 1, "include_graph": False},
        )
    assert r1.status_code == 200
    assert r2.status_code == 200
    assert r1.json()["graph"] is not None
    assert r2.json()["graph"] is None
