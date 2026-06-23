"""Tests for BaseRepository."""

import asyncio
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import httpx

from app.repositories.base import (
    BaseRepository,
    RepositoryError,
    RepositoryRateLimited,
    RepositoryServerError,
    RepositoryTimeout,
)


def _mock_response(status_code, json_data=None):
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status_code
    resp.json.return_value = json_data or {}
    resp.url = "http://test.local/api"
    return resp


@pytest.fixture
def repo():
    return BaseRepository(timeout=5, max_retries=3)


def test_get_success(repo):
    resp = _mock_response(200, {"ok": True})
    with patch.object(repo, "_get_client") as mock_client:
        client = AsyncMock()
        client.request.return_value = resp
        mock_client.return_value = client
        result = asyncio.get_event_loop().run_until_complete(repo._get("http://test.local/api"))
    assert result == {"ok": True}


def test_post_success(repo):
    resp = _mock_response(200, {"id": 1})
    with patch.object(repo, "_get_client") as mock_client:
        client = AsyncMock()
        client.request.return_value = resp
        mock_client.return_value = client
        result = asyncio.get_event_loop().run_until_complete(repo._post("http://test.local/api", json={"x": 1}))
    assert result == {"id": 1}


def test_rate_limited(repo):
    resp = _mock_response(429)
    with patch.object(repo, "_get_client") as mock_client:
        client = AsyncMock()
        client.request.return_value = resp
        mock_client.return_value = client
        with pytest.raises(RepositoryRateLimited):
            asyncio.get_event_loop().run_until_complete(repo._get("http://test.local/api"))


def test_server_error(repo):
    resp = _mock_response(500)
    with patch.object(repo, "_get_client") as mock_client:
        client = AsyncMock()
        client.request.return_value = resp
        mock_client.return_value = client
        with pytest.raises(RepositoryServerError):
            asyncio.get_event_loop().run_until_complete(repo._get("http://test.local/api"))


def test_timeout(repo):
    with patch.object(repo, "_get_client") as mock_client:
        client = AsyncMock()
        client.request.side_effect = httpx.TimeoutException("timed out")
        mock_client.return_value = client
        with pytest.raises(RepositoryTimeout):
            asyncio.get_event_loop().run_until_complete(repo._get("http://test.local/api"))


def test_retry_on_5xx(repo):
    resp_500 = _mock_response(500)
    resp_200 = _mock_response(200, {"recovered": True})
    with patch.object(repo, "_get_client") as mock_client:
        client = AsyncMock()
        client.request.side_effect = [resp_500, resp_500, resp_200]
        mock_client.return_value = client
        result = asyncio.get_event_loop().run_until_complete(repo._get("http://test.local/api"))
    assert result == {"recovered": True}
    assert client.request.call_count == 3
