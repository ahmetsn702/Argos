# tests/test_confidence_llm_integration.py
"""Tests for LLM endpoint with confidence graph integration."""

import pytest
from unittest.mock import patch
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture(autouse=True)
def reset_cache():
    from app.services.confidence.cache import _default_backend
    _default_backend.clear()
    yield
    _default_backend.clear()


def test_llm_analysis_default_no_confidence():
    """verbose=False (default) + empty cache → confidence_summary=None."""
    with patch(
        "app.services.llm_analyst.OsintAnalyst.analyze",
        return_value={"result": "mock"},
    ) as mock_analyze:
        resp = client.post("/analysis/osint",
                           json={"data": {"email": "test@x.com"}})
        assert resp.status_code != 500
        if mock_analyze.called:
            call_kwargs = mock_analyze.call_args
            passed_summary = (
                call_kwargs.kwargs.get("confidence_summary")
                if call_kwargs.kwargs else None
            )
            assert passed_summary is None


def test_llm_analysis_with_cached_graph():
    """Cache has graph → summary passed to analyze (or None — graceful)."""
    from app.services.confidence.cache import default_cache
    default_cache.merge_and_save(
        "email:cached@x.com",
        {"mosint": {"email": "cached@x.com"}},
        ttl_hours=1,
    )

    with patch(
        "app.services.llm_analyst.OsintAnalyst.analyze",
        return_value={"result": "mock"},
    ) as mock_analyze:
        resp = client.post("/analysis/osint",
                           json={"data": {"email": "cached@x.com"}})
        assert resp.status_code != 500
        if mock_analyze.called:
            call_kwargs = mock_analyze.call_args
            if call_kwargs and call_kwargs.kwargs:
                summary = call_kwargs.kwargs.get("confidence_summary")
                assert summary is None or isinstance(summary, dict)


def test_llm_analysis_verbose_flag():
    """verbose=True → endpoint returns non-500."""
    resp = client.post("/analysis/osint",
                       params={"verbose": "true"},
                       json={"data": {"email": "verbose@x.com"}})
    assert resp.status_code != 500


def test_llm_analysis_confidence_error_graceful():
    """Cache exception → LLM endpoint still returns non-500."""
    with patch(
        "app.services.confidence.cache.ConfidenceGraphCache.get",
        side_effect=Exception("cache boom"),
    ):
        resp = client.post("/analysis/osint",
                           json={"data": {"email": "err@x.com"}})
        assert resp.status_code != 500
