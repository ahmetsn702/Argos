# tests/test_correlation_entity.py
"""Tests for /correlation/identity (Phase 1 of correlation engine)."""
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _profile(platform, username, display_name=None, bio=None):
    """Helper: build a ProfileInput dict for the JSON body."""
    return {
        "platform": platform,
        "username": username,
        "display_name": display_name,
        "bio": bio,
    }


def test_identity_likely_same_high_signals():
    """High bio overlap + same display name + similar username → likely_same."""
    payload = {
        "profiles": [
            _profile(
                "instagram", "alicesmith", "Alice Smith",
                "Software engineer in Istanbul. Coffee cats and code.",
            ),
            _profile(
                "x", "alice_smith", "Alice Smith",
                "Software engineer in Istanbul. Loves coffee cats code.",
            ),
        ],
    }
    r = client.post("/correlation/identity", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["pairs_evaluated"] == 1
    assert len(data["matches"]) == 1
    m = data["matches"][0]
    assert m["verdict"] == "likely_same"
    assert m["confidence"] >= 0.7
    assert m["entity_a"] == "profile:instagram:alicesmith"
    assert m["entity_b"] == "profile:x:alice_smith"
    assert "bio_score" in m["signals"]
    assert "name_score" in m["signals"]
    assert "username_score" in m["signals"]


def test_identity_unlikely_different_people():
    """Different name + different bio + different username → unlikely."""
    payload = {
        "profiles": [
            _profile("instagram", "alice_92", "Alice Smith", "Photographer in Berlin."),
            _profile("x", "bobjones", "Bob Jones", "Football fan from London."),
        ],
    }
    r = client.post("/correlation/identity", json=payload)
    assert r.status_code == 200
    m = r.json()["matches"][0]
    assert m["verdict"] == "unlikely"
    assert m["confidence"] < 0.55


def test_identity_unclear_partial_signals():
    """Same name + different bio + similar username (digit suffix) → unclear."""
    payload = {
        "profiles": [
            _profile("instagram", "alicesmith", "Alice Smith", "Photographer based in Berlin"),
            _profile("x", "alicesmith2", "Alice Smith", "Software engineer in Istanbul"),
        ],
    }
    r = client.post("/correlation/identity", json=payload)
    assert r.status_code == 200
    m = r.json()["matches"][0]
    assert m["verdict"] == "unclear"
    assert 0.50 <= m["confidence"] < 0.68
    # Username similarity should detect digit-suffix → 0.85
    assert m["signals"]["username_score"] >= 0.85


def test_identity_turkish_name_normalization():
    """'Ahmet Şahin' should match 'Ahmet Sahin' (Turkish character folding)."""
    payload = {
        "profiles": [
            _profile(
                "instagram", "ahmettssyn", "Ahmet Şahin",
                "müzisyen istanbul müzik prodüksiyon",
            ),
            _profile(
                "x", "ahmettssyn", "Ahmet Sahin",
                "müzisyen istanbul müzik prodüksiyon",
            ),
        ],
    }
    r = client.post("/correlation/identity", json=payload)
    assert r.status_code == 200
    m = r.json()["matches"][0]
    assert m["verdict"] == "likely_same"
    # name_score must be 1.0 after Turkish folding
    assert m["signals"]["name_score"] == 1.0
    assert "display name eşit" in m["evidence"]


def test_identity_three_profiles_yields_three_pairs():
    """N=3 profiles → C(3,2) = 3 pairwise matches."""
    payload = {
        "profiles": [
            _profile("instagram", "u1", "User One", "bio one"),
            _profile("x", "u2", "User Two", "bio two"),
            _profile("github", "u3", "User Three", "bio three"),
        ],
    }
    r = client.post("/correlation/identity", json=payload)
    assert r.status_code == 200
    data = r.json()
    assert data["pairs_evaluated"] == 3
    assert len(data["matches"]) == 3
    # All pair IDs should be unique (no duplicate pairs)
    pair_keys = {(m["entity_a"], m["entity_b"]) for m in data["matches"]}
    assert len(pair_keys) == 3


def test_identity_too_few_profiles_returns_400():
    """Single profile cannot be compared → 400."""
    payload = {
        "profiles": [_profile("instagram", "alice", "Alice", "bio")],
    }
    r = client.post("/correlation/identity", json=payload)
    assert r.status_code == 400
    assert "At least 2" in r.json().get("detail", "")


def test_identity_empty_bios_does_not_crash():
    """Empty/None bios must not raise; relies on name+username only."""
    payload = {
        "profiles": [
            _profile("instagram", "alice", "Alice Smith", ""),
            _profile("x", "alice", "Alice Smith", None),
        ],
    }
    r = client.post("/correlation/identity", json=payload)
    assert r.status_code == 200
    m = r.json()["matches"][0]
    # bio_score must be 0 (no content) but pair must still resolve
    assert m["signals"]["bio_score"] == 0.0
    assert m["signals"]["name_score"] == 1.0
    assert m["signals"]["username_score"] == 1.0
    # With name+username = 1.0, bio = 0 → confidence ≈ 0.55, expect unclear band
    assert m["verdict"] in ("likely_same", "unclear")


def test_identity_handles_long_unicode_bios():
    """Long unicode-heavy bios must not crash the resolver."""
    long_bio = ("İstanbul'da yaşıyorum. " * 50) + "Software engineer 🇹🇷 ✨"
    payload = {
        "profiles": [
            _profile("instagram", "user_a", "Test User", long_bio),
            _profile("x", "user_b", "Different Name", long_bio),
        ],
    }
    r = client.post("/correlation/identity", json=payload)
    assert r.status_code == 200
    m = r.json()["matches"][0]
    # Identical bio → high bio_score even if names differ
    assert m["signals"]["bio_score"] >= 0.9
    assert m["confidence"] > 0.0
