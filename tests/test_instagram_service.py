# tests/test_instagram_service.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.services.instagram_service import InstagramService


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _bio_payload(username="test", bio="hello", full_name="Test User", source="api"):
    return {"username": username, "biography": bio, "full_name": full_name, "source": source}


def test_get_bio_cache_miss():
    """Cache miss → get_instagram_bio is called and result is cached."""
    svc = InstagramService()
    svc._cache_manager._memory.clear()
    payload = _bio_payload()

    with patch("app.services.instagram_service.get_instagram_bio", new=AsyncMock(return_value=payload)):
        result = _run(svc.get_bio("test"))

    assert result["biography"] == "hello"
    # Value is now in cache
    assert _run(svc.cache_get(svc.cache_key("bio", "test"))) is not None


def test_get_bio_cache_hit():
    """Cache hit → get_instagram_bio is NOT called a second time."""
    svc = InstagramService()
    svc._cache_manager._memory.clear()
    payload = _bio_payload()

    with patch("app.services.instagram_service.get_instagram_bio", new=AsyncMock(return_value=payload)) as mock_fn:
        _run(svc.get_bio("test"))   # populates cache
        _run(svc.get_bio("test"))   # should hit cache
        assert mock_fn.call_count == 1


def test_get_bio_not_found():
    """Repo returns not_found → service returns error dict."""
    svc = InstagramService()
    svc._cache_manager._memory.clear()

    with patch("app.services.instagram_service.get_instagram_bio",
               new=AsyncMock(return_value={"error": "not_found"})):
        result = _run(svc.get_bio("ghost"))

    assert "error" in result
    assert result["error"] == "not_found"


def test_get_profile_success():
    """get_profile wraps get_bio result into profile shape."""
    svc = InstagramService()
    svc._cache_manager._memory.clear()
    payload = _bio_payload(username="alice", bio="dev", full_name="Alice")

    with patch("app.services.instagram_service.get_instagram_bio", new=AsyncMock(return_value=payload)):
        result = _run(svc.get_profile("alice"))

    assert result["username"] == "alice"
    assert result["status"] == "exists"
    assert result["bio"] == "dev"
