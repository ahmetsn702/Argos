"""Tests for app/services/temporal/parsing.py and constants.py"""

from datetime import datetime

import pytest

from app.services.temporal.parsing import is_night, parse_temporal, to_local


# --- parse_temporal -----------------------------------------------------------

def test_parse_iso8601_with_z():
    dt = parse_temporal("2020-06-15T03:00:00Z")
    assert dt == datetime(2020, 6, 15, 3, 0, 0)
    assert dt.tzinfo is None  # naive UTC


def test_parse_iso8601_naive():
    dt = parse_temporal("2021-03-10T12:30:00")
    assert dt == datetime(2021, 3, 10, 12, 30, 0)


def test_parse_date_only():
    dt = parse_temporal("2020-01-01")
    assert dt == datetime(2020, 1, 1, 0, 0, 0)


def test_parse_slash_format():
    # %d/%m/%Y: day=01, month=06, year=2022 → 1 June 2022
    dt = parse_temporal("01/06/2022")
    assert dt == datetime(2022, 6, 1, 0, 0, 0)


def test_parse_none_returns_none():
    assert parse_temporal(None) is None


def test_parse_empty_string_returns_none():
    assert parse_temporal("") is None


def test_parse_garbage_returns_none():
    assert parse_temporal("not-a-date-at-all!!") is None


# --- is_night -----------------------------------------------------------------

def test_is_night_true_utc_to_local():
    # UTC 21:00 + offset=3 → local 00:00 → night [0,6)
    dt = datetime(2024, 1, 1, 21, 0, 0)
    assert is_night(dt, offset_hours=3, start=0, end=6) is True


def test_is_night_false_daytime():
    # UTC 06:00 + offset=3 → local 09:00 → not night
    dt = datetime(2024, 1, 1, 6, 0, 0)
    assert is_night(dt, offset_hours=3, start=0, end=6) is False


def test_is_night_boundary_start():
    # UTC 21:00 + offset=3 → local 00:00 → exactly on start boundary → True
    dt = datetime(2024, 1, 1, 21, 0, 0)
    assert is_night(dt, offset_hours=3, start=0, end=6) is True


def test_is_night_boundary_end():
    # UTC 03:00 + offset=3 → local 06:00 → at end boundary (exclusive) → False
    dt = datetime(2024, 1, 1, 3, 0, 0)
    assert is_night(dt, offset_hours=3, start=0, end=6) is False


# --- constants reload ---------------------------------------------------------

def test_constants_reload_picks_up_env(monkeypatch):
    monkeypatch.setenv("TEMPORAL_CLUSTER_WINDOW_MIN", "999")
    import app.services.temporal.constants as C
    C.reload()
    assert C.CLUSTER_WINDOW_MIN == 999
    # restore
    monkeypatch.delenv("TEMPORAL_CLUSTER_WINDOW_MIN", raising=False)
    C.reload()
    assert C.CLUSTER_WINDOW_MIN == 60
