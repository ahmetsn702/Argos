import pytest
import asyncio
import logging
from unittest.mock import MagicMock
from app.models.watchlist import WatchlistAlert
from app.services.watchlist.notifiers.base import NotifierBase
from app.services.watchlist.notifiers.log_notifier import LogNotifier

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

def test_base_abc_instantiation():
    with pytest.raises(TypeError):
        NotifierBase()

def test_notifier_subclass():
    class DummyNotifier(NotifierBase):
        async def notify(self, alert: WatchlistAlert) -> None:
            pass
    dn = DummyNotifier()
    assert isinstance(dn, NotifierBase)

def test_notifier_subclass_missing_notify():
    with pytest.raises(TypeError):
        class BadNotifier(NotifierBase):
            pass
        BadNotifier()

def test_log_notifier_notify_info_called(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=1,
        target_id=10,
        title="Test Alert",
        severity="high",
        message="This is a test message",
        timestamp="2026-05-22T20:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    assert mock_logger.info.call_count == 1

def test_log_notifier_log_format(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=2,
        target_id=20,
        title="Format Test",
        severity="medium",
        message="Checking formats",
        timestamp="2026-05-22T21:00:00",
        is_read=True
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once_with(
        "Watchlist Alert [%s] Target ID %d (Severity: %s): %s - %s",
        "2026-05-22T21:00:00",
        20,
        "medium",
        "Format Test",
        "Checking formats"
    )

def test_log_notifier_low_severity(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=3,
        target_id=30,
        title="Low Severity",
        severity="low",
        message="Minor change",
        timestamp="2026-05-22T22:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args[0][3] == "low"

def test_log_notifier_medium_severity(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=4,
        target_id=40,
        title="Medium Severity",
        severity="medium",
        message="Moderate change",
        timestamp="2026-05-22T23:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args[0][3] == "medium"

def test_log_notifier_high_severity(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=5,
        target_id=50,
        title="High Severity",
        severity="high",
        message="Significant change",
        timestamp="2026-05-23T00:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args[0][3] == "high"

def test_log_notifier_critical_severity(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=6,
        target_id=60,
        title="Critical Severity",
        severity="critical",
        message="Critical change",
        timestamp="2026-05-23T01:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args[0][3] == "critical"

def test_log_notifier_empty_fields(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=7,
        target_id=70,
        title="",
        severity="",
        message="",
        timestamp="",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once_with(
        "Watchlist Alert [%s] Target ID %d (Severity: %s): %s - %s",
        "",
        70,
        "",
        "",
        ""
    )

def test_log_notifier_negative_target_id(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=8,
        target_id=-1,
        title="Negative Target ID",
        severity="low",
        message="Target ID is negative",
        timestamp="2026-05-23T02:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args[0][2] == -1

def test_log_notifier_large_target_id(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=9,
        target_id=999999999,
        title="Large Target ID",
        severity="low",
        message="Target ID is very large",
        timestamp="2026-05-23T03:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args[0][2] == 999999999

def test_log_notifier_special_characters_title(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=10,
        target_id=100,
        title="Title with specia!@#$%^&*()_+ l characters",
        severity="high",
        message="Checking special characters",
        timestamp="2026-05-23T04:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert "specia!@#$%^&*" in mock_logger.info.call_args[0][4]

def test_log_notifier_special_characters_message(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=11,
        target_id=110,
        title="Special Message",
        severity="high",
        message="Message with specia!@#$%^&*()_+ l characters",
        timestamp="2026-05-23T05:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert "specia!@#$%^&*" in mock_logger.info.call_args[0][5]

def test_log_notifier_utc_timestamp(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=12,
        target_id=120,
        title="UTC Test",
        severity="low",
        message="UTC timezone check",
        timestamp="2026-05-23T06:00:00Z",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert mock_logger.info.call_args[0][1] == "2026-05-23T06:00:00Z"

def test_log_notifier_is_read_true(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=13,
        target_id=130,
        title="Read Alert",
        severity="low",
        message="Alert is already read",
        timestamp="2026-05-23T07:00:00",
        is_read=True
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert alert.is_read is True

def test_log_notifier_is_read_false(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert = WatchlistAlert(
        id=14,
        target_id=140,
        title="Unread Alert",
        severity="low",
        message="Alert is not read",
        timestamp="2026-05-23T08:00:00",
        is_read=False
    )
    _run(notifier.notify(alert))
    mock_logger.info.assert_called_once()
    assert alert.is_read is False

def test_log_notifier_multiple_alerts(monkeypatch):
    mock_logger = MagicMock()
    monkeypatch.setattr("app.services.watchlist.notifiers.log_notifier.logger", mock_logger)
    
    notifier = LogNotifier()
    alert1 = WatchlistAlert(
        id=15,
        target_id=150,
        title="First Alert",
        severity="low",
        message="First message",
        timestamp="2026-05-23T09:00:00",
        is_read=False
    )
    alert2 = WatchlistAlert(
        id=16,
        target_id=160,
        title="Second Alert",
        severity="high",
        message="Second message",
        timestamp="2026-05-23T09:05:00",
        is_read=False
    )
    _run(notifier.notify(alert1))
    _run(notifier.notify(alert2))
    assert mock_logger.info.call_count == 2

def test_log_notifier_subclass_check():
    notifier = LogNotifier()
    assert isinstance(notifier, NotifierBase)
