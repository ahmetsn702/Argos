import importlib
import pytest


def _reload_flags():
    import app.core.feature_flags as ff
    importlib.reload(ff)
    return ff


def test_all_flags_default_false(monkeypatch):
    for key in ("GRAPH_DB_ENABLED", "WATCHLIST_ENABLED",
                "AGENT_ENABLED", "MALTEGO_ENABLED"):
        monkeypatch.delenv(key, raising=False)
    ff = _reload_flags()
    assert ff.GRAPH_DB_ENABLED is False
    assert ff.WATCHLIST_ENABLED is False
    assert ff.AGENT_ENABLED is False
    assert ff.MALTEGO_ENABLED is False


def test_graph_db_flag_from_env(monkeypatch):
    monkeypatch.setenv("GRAPH_DB_ENABLED", "true")
    ff = _reload_flags()
    assert ff.GRAPH_DB_ENABLED is True


def test_agent_flag_from_env(monkeypatch):
    monkeypatch.setenv("AGENT_ENABLED", "1")
    ff = _reload_flags()
    assert ff.AGENT_ENABLED is True


def test_watchlist_flag_from_env(monkeypatch):
    monkeypatch.setenv("WATCHLIST_ENABLED", "yes")
    ff = _reload_flags()
    assert ff.WATCHLIST_ENABLED is True


def test_maltego_flag_from_env(monkeypatch):
    monkeypatch.setenv("MALTEGO_ENABLED", "on")
    ff = _reload_flags()
    assert ff.MALTEGO_ENABLED is True
