# tests/test_person_aggregator.py
"""Unit tests for app.services.person_aggregator.

These tests mock internal downstream services so they do not hit the network.
They verify:
  * `_scan_username` calls the Direct Instagram service.
  * `build_person_card` returns a PersonCard-shaped object even on
    minimal/empty downstream data.
  * The aggregator's cache short-circuits a second identical call.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict
from unittest.mock import AsyncMock, patch

from app.models.person import PersonHints, PersonQuery
from app.services.person_aggregator import (
    _LOCAL_CACHE,
    _scan_email,
    _scan_username,
    build_person_card,
)


def _empty_legacy_result(verdict: str = "partial") -> Dict[str, Any]:
    return {
        "input": {"email": None, "username": "x", "phone": None},
        "results": {"social": {"ok": True, "data": {"results": []}}},
        "verdict": verdict,
        "took_ms": 1,
    }


def _clear_aggregator_cache() -> None:
    _LOCAL_CACHE.clear()


def test_scan_username_calls_instagram_service() -> None:
    """`_scan_username` must call `fetch_bio_instagram`."""
    with patch(
        "app.services.instagram_service.fetch_bio_instagram",
        new=AsyncMock(return_value={"status": "exists", "url": "https://www.instagram.com/testuser/", "display_name": "Insta", "bio": "Bio"}),
    ) as mock_ig:
        out = asyncio.run(_scan_username("http://ignored", "testuser", timeout=5))

    mock_ig.assert_awaited_once_with("testuser")

    assert out["verdict"] == "ok"
    assert len(out["results"]["social"]["data"]["results"]) == 1


def test_scan_email_uses_in_process_helper() -> None:
    fake = _empty_legacy_result("ok")
    with patch(
        "app.routers.unified._scan_full_legacy",
        new=AsyncMock(return_value=fake),
    ) as mocked:
        out = asyncio.run(_scan_email("http://ignored", "user@example.com", timeout=5))
    assert out == fake
    mocked.assert_awaited_once()
    # Mock was called with email kwarg, not username.
    kwargs = mocked.await_args.kwargs
    assert kwargs.get("email") == "user@example.com"
    assert kwargs.get("username") is None


def test_scan_username_does_not_make_http_call() -> None:
    """Sanity: no httpx.AsyncClient instantiation when scanning usernames with mocked services."""
    with patch("httpx.AsyncClient") as mock_client, patch(
        "app.services.instagram_service.fetch_bio_instagram",
        new=AsyncMock(return_value={"status": "not_found"}),
    ):
        asyncio.run(_scan_username("http://ignored", "u", timeout=5))
    mock_client.assert_not_called()


def test_scan_username_swallows_helper_exception() -> None:
    """If the services raise, _scan_username returns a fail envelope."""
    async def _boom(*_args, **_kwargs) -> Any:
        raise RuntimeError("kaboom")

    with patch("app.services.instagram_service.fetch_bio_instagram", new=_boom):
        out = asyncio.run(_scan_username("http://ignored", "u", timeout=5))
    assert out["verdict"] == "fail"
    assert "kaboom" in out["error"]
    assert out["input"]["username"] == "u"


def test_build_person_card_returns_personcard_shape() -> None:
    """End-to-end shape check with mocked downstream and no CSE keys."""
    _clear_aggregator_cache()
    with patch(
        "app.services.person_aggregator._scan_username",
        new=AsyncMock(return_value=_empty_legacy_result("partial")),
    ):
        q = PersonQuery(
            first_name=f"Ali{int(time.time()*1000)}",  # unique, sidesteps stale cache
            last_name="Veli",
            hometown="Istanbul",
            fast=True,
            max_scans=2,
            timeout=10,
        )
        card = asyncio.run(build_person_card(q, base_url="http://ignored"))
    assert card.verdict in {"ok", "partial", "fail"}
    assert isinstance(card.profiles, list)
    assert isinstance(card.sources, list)
    assert card.query["first_name"] == q.first_name
    assert card.query["last_name"] == "Veli"


def test_build_person_card_with_email_hints() -> None:
    """Hints.emails should be echoed back through the email scan path."""
    _clear_aggregator_cache()
    fake = {
        "input": {"email": "h@x.com", "username": None, "phone": None},
        "results": {"mosint": {"ok": True, "data": {}}},
        "verdict": "partial",
        "took_ms": 1,
    }
    with patch(
        "app.routers.unified._scan_full_legacy",
        new=AsyncMock(return_value=fake),
    ), patch(
        "app.services.person_aggregator._scan_username",
        new=AsyncMock(return_value=_empty_legacy_result("partial")),
    ):
        q = PersonQuery(
            first_name=f"Hint{int(time.time()*1000)}",  # unique
            last_name="Test",
            hometown="X",
            hints=PersonHints(emails=["h@x.com"], usernames=[], phones=[]),
            fast=False,  # email scans only run when fast=False
            max_scans=1,
            timeout=10,
        )
        card = asyncio.run(build_person_card(q, base_url="http://ignored"))
    # The aggregator stores `[{email, result}]` pairs.
    assert any(e.get("email") == "h@x.com" for e in card.emails)


def test_build_person_card_cache_hit_skips_helper() -> None:
    """Second identical call must hit the aggregator cache (no extra helper calls)."""
    _clear_aggregator_cache()
    call_count = {"n": 0}

    async def counting_helper(*_args, **_kw: Any) -> Dict[str, Any]:
        call_count["n"] += 1
        return _empty_legacy_result("partial")

    with patch("app.services.person_aggregator._scan_username", new=counting_helper):
        q = PersonQuery(
            first_name=f"Cache{int(time.time()*1000)}",
            last_name="Test",
            hometown="X",
            fast=True,
            max_scans=1,
            timeout=10,
        )
        asyncio.run(build_person_card(q, base_url="http://ignored"))
        n_after_first = call_count["n"]
        asyncio.run(build_person_card(q, base_url="http://ignored"))
    assert call_count["n"] == n_after_first, (
        f"cache miss: helper called {call_count['n']} times "
        f"(expected stable {n_after_first})"
    )


def test_build_person_card_fallback_cse_failure() -> None:
    """If CSE fails or is bypassed, we still scan hints.usernames and name variants,
    and sources list shows ok=False and reason=api_key_invalid for cse."""
    _clear_aggregator_cache()

    with patch.dict("os.environ", {"GOOGLE_CSE_API_KEY": "", "GOOGLE_CSE_CX": ""}):
        q = PersonQuery(
            first_name="ahmet",
            last_name="sayin",
            hometown="X",
            hints=PersonHints(usernames=["ahmettssyn"]),
            fast=True,
            max_scans=5,
            timeout=10,
        )

        with patch(
            "app.services.person_aggregator._scan_username",
            new=AsyncMock(return_value=_empty_legacy_result("partial")),
        ):
            card = asyncio.run(build_person_card(q, base_url="http://ignored"))

            # Verify CSE source info
            cse_source = next((s for s in card.sources if s.type == "cse"), None)
            assert cse_source is not None
            assert cse_source.ok is False
            assert cse_source.reason == "api_key_invalid"

            # Verify that social_scan:ahmettssyn was called/scanned
            scan_ahmettssyn = next((s for s in card.sources if s.type == "social_scan:ahmettssyn"), None)
            assert scan_ahmettssyn is not None

            # Also verify name variants were scanned (e.g. ahmetsayin, ahmtsyn, etc.)
            scan_variants = [s for s in card.sources if s.type.startswith("social_scan:") and s.type != "social_scan:ahmettssyn"]
            assert len(scan_variants) > 0


def test_build_person_card_cse_http_403() -> None:
    """Verify that a 403 response from CSE is correctly handled as ok=False, reason=api_key_invalid."""
    import httpx
    _clear_aggregator_cache()

    with patch.dict("os.environ", {"GOOGLE_CSE_API_KEY": "somekey", "GOOGLE_CSE_CX": "somecx"}):
        q = PersonQuery(
            first_name="ahmet",
            last_name="sayin",
            hometown="X",
            hints=PersonHints(usernames=["ahmettssyn"]),
            fast=True,
            max_scans=5,
            timeout=10,
        )

        mock_response = httpx.Response(403, json={"error": "forbidden"})

        with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get, patch(
            "app.services.person_aggregator._scan_username",
            new=AsyncMock(return_value=_empty_legacy_result("partial")),
        ):
            mock_get.return_value = mock_response
            card = asyncio.run(build_person_card(q, base_url="http://ignored"))

            cse_source = next((s for s in card.sources if s.type == "cse"), None)
            assert cse_source is not None
            assert cse_source.ok is False
            assert cse_source.reason == "api_key_invalid"

            # Verify that social_scan:ahmettssyn still ran
            scan_ahmettssyn = next((s for s in card.sources if s.type == "social_scan:ahmettssyn"), None)
            assert scan_ahmettssyn is not None


def test_build_person_card_instagram_profile_found() -> None:
    """Verify that when providing hint 'ahmettssyn', build_person_card scans and finds the Instagram profile."""
    _clear_aggregator_cache()

    q = PersonQuery(
        first_name="ahmet",
        last_name="sayin",
        hometown="X",
        hints=PersonHints(usernames=["ahmettssyn"]),
        fast=True,
        max_scans=5,
        timeout=10,
    )

    with patch(
        "app.services.instagram_service.fetch_bio_instagram",
        new=AsyncMock(return_value={"status": "exists", "url": "https://www.instagram.com/ahmettssyn/", "display_name": "Ahmet Sayin", "bio": "Hello instagram"}),
    ) as mock_ig:
        card = asyncio.run(build_person_card(q, base_url="http://ignored"))

        # Verify services were called
        mock_ig.assert_awaited()

        # Verify that the Instagram profile was found and exists in profiles list
        ig_profile = next((p for p in card.profiles if p.platform == "instagram"), None)
        assert ig_profile is not None
        assert ig_profile.handle == "ahmettssyn"
        assert ig_profile.url == "https://www.instagram.com/ahmettssyn/"
        assert ig_profile.status == "exists"


def test_build_person_card_instagram_429_treated_as_exists() -> None:
    """Verify that when Instagram service responds with 429 rate limit, it is treated as status=exists."""
    _clear_aggregator_cache()

    q = PersonQuery(
        first_name="ahmet",
        last_name="sayin",
        hometown="X",
        hints=PersonHints(usernames=["ahmettssyn"]),
        fast=True,
        max_scans=5,
        timeout=10,
    )

    with patch(
        "app.services.instagram_service.fetch_bio_instagram",
        new=AsyncMock(return_value={"status": "429", "url": "https://www.instagram.com/ahmettssyn/", "display_name": "", "bio": ""}),
    ) as mock_ig:
        card = asyncio.run(build_person_card(q, base_url="http://ignored"))

        # Verify that the Instagram profile was treated as status=exists
        ig_profile = next((p for p in card.profiles if p.platform == "instagram"), None)
        assert ig_profile is not None
        assert ig_profile.handle == "ahmettssyn"
        assert ig_profile.status == "exists"
