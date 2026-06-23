"""Tests for app/services/temporal/narrator.py"""

import asyncio
import json
from datetime import datetime
from unittest.mock import MagicMock, patch

from app.models.temporal import AnomalyFlag, AnomalySeverity, AnomalyType, TimelineEvent, TimelineEventType
from app.services.temporal.narrator import TemporalNarrator


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)


def _ev() -> TimelineEvent:
    return TimelineEvent(
        event_id="ev1", finding_id="f1",
        event_type=TimelineEventType.BREACH,
        timestamp=datetime(2021, 1, 1),
        confidence=0.8, source="hibp",
    )


def _flag() -> AnomalyFlag:
    return AnomalyFlag(
        anomaly_id="a1", type=AnomalyType.NIGHT_ACTIVITY,
        severity=AnomalySeverity.LOW,
        event_ids=["ev1"], explanation="Gece aktivitesi.",
    )


def test_no_api_key_returns_none(monkeypatch):
    monkeypatch.setattr("app.core.config.settings.GOOGLE_API_KEY", "")
    result = _run(TemporalNarrator().generate([_ev()], [_flag()]))
    assert result is None


def test_valid_response_returns_narrative():
    good_json = json.dumps({
        "summary": "Test özeti.",
        "risk_level": "medium",
        "key_observations": ["Gece aktivitesi var."],
    })
    mock_response = MagicMock()
    mock_response.text = good_json

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.core.config.settings.GOOGLE_API_KEY", "fake-key"), \
         patch("google.genai.Client", return_value=mock_client):
        result = _run(TemporalNarrator().generate([_ev()], [_flag()]))

    assert result is not None
    assert result.summary == "Test özeti."
    assert result.risk_level == "medium"
    assert result.model == TemporalNarrator.MODEL


def test_malformed_json_returns_none():
    mock_response = MagicMock()
    mock_response.text = "not valid json {{{"

    mock_client = MagicMock()
    mock_client.models.generate_content.return_value = mock_response

    with patch("app.core.config.settings.GOOGLE_API_KEY", "fake-key"), \
         patch("google.genai.Client", return_value=mock_client):
        result = _run(TemporalNarrator().generate([_ev()], [_flag()]))

    assert result is None


def test_genai_exception_returns_none():
    mock_client = MagicMock()
    mock_client.models.generate_content.side_effect = RuntimeError("API down")

    with patch("app.core.config.settings.GOOGLE_API_KEY", "fake-key"), \
         patch("google.genai.Client", return_value=mock_client):
        result = _run(TemporalNarrator().generate([_ev()], [_flag()]))

    assert result is None
