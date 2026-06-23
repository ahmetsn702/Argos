# tests/repositories/test_instagram_repo.py
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
import httpx
import pytest
from app.repositories.instagram_repo import InstagramRepository
from app.repositories.base import RepositoryTimeout


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _mock_response(status: int, json_data=None, text: str = "") -> MagicMock:
    r = MagicMock(spec=httpx.Response)
    r.status_code = status
    r.text = text or ""
    if json_data is not None:
        r.json = MagicMock(return_value=json_data)
    return r


def test_fetch_profile_api_success():
    """200 → dict with status_code and data."""
    repo = InstagramRepository()
    payload = {"data": {"user": {"biography": "hello", "full_name": "Test"}}}
    mock_resp = _mock_response(200, json_data=payload)

    with patch.object(repo, "_retry_get", new=AsyncMock(return_value=mock_resp)):
        with patch("httpx.AsyncClient") as mock_cls:
            mock_cls.return_value.__aenter__ = AsyncMock(return_value=MagicMock())
            mock_cls.return_value.__aexit__ = AsyncMock(return_value=False)
            # Direct patch on async context
            result = _run(repo.fetch_profile_api("testuser"))

    # _retry_get was patched so result comes from mock
    assert result["status_code"] == 200
    assert "data" in result


def test_fetch_profile_api_404():
    """404 → {"status_code": 404}."""
    repo = InstagramRepository()
    mock_resp = _mock_response(404)

    with patch.object(repo, "_retry_get", new=AsyncMock(return_value=mock_resp)):
        with patch("httpx.AsyncClient") as mock_cls:
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx
            result = _run(repo.fetch_profile_api("ghost"))

    assert result["status_code"] == 404


def test_fetch_profile_html_success():
    """200 → non-empty HTML string."""
    repo = InstagramRepository()
    html_content = "<html><body>test profile</body></html>"
    mock_resp = _mock_response(200, text=html_content)

    with patch.object(repo, "_retry_get", new=AsyncMock(return_value=mock_resp)):
        with patch("httpx.AsyncClient") as mock_cls:
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx
            result = _run(repo.fetch_profile_html("testuser"))

    assert isinstance(result, str)
    assert "test profile" in result


def test_fetch_via_jina_success():
    """200 → string content returned."""
    repo = InstagramRepository()
    mock_resp = _mock_response(200, text="jina content here")

    async def _fake_get(url, **kwargs):
        return mock_resp

    with patch("httpx.AsyncClient") as mock_cls:
        ctx = MagicMock()
        ctx.__aenter__ = AsyncMock(return_value=ctx)
        ctx.__aexit__ = AsyncMock(return_value=False)
        ctx.get = AsyncMock(return_value=mock_resp)
        mock_cls.return_value = ctx
        result = _run(repo.fetch_via_jina("testuser"))

    assert isinstance(result, str)
    assert "jina content" in result


def test_fetch_timeout():
    """httpx.TimeoutException propagates from _retry_get."""
    repo = InstagramRepository()

    with patch.object(repo, "_retry_get", new=AsyncMock(side_effect=httpx.TimeoutException("t"))):
        with patch("httpx.AsyncClient") as mock_cls:
            ctx = MagicMock()
            ctx.__aenter__ = AsyncMock(return_value=ctx)
            ctx.__aexit__ = AsyncMock(return_value=False)
            mock_cls.return_value = ctx
            # fetch_profile_api does not catch timeout — it propagates
            with pytest.raises(httpx.TimeoutException):
                _run(repo.fetch_profile_api("testuser"))
