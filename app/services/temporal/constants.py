"""Temporal Intelligence thresholds — all ENV-overridable."""

import os


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


def reload() -> None:
    """Re-read ENV values into module-level constants. Call after monkeypatching in tests."""
    global TTL_HOURS, NIGHT_TZ_OFFSET, NIGHT_START_HOUR, NIGHT_END_HOUR
    global CLUSTER_WINDOW_MIN
    global BURST_MIN_PLATFORMS, BURST_MED_PLATFORMS, BURST_HIGH_PLATFORMS
    global NIGHT_LOW_EVENTS, NIGHT_MED_EVENTS, NIGHT_HIGH_EVENTS
    global SILENCE_DAYS, BREACH_OVERLAP_DAYS

    TTL_HOURS = _float("TEMPORAL_TTL_HOURS", 6.0)
    NIGHT_TZ_OFFSET = _int("TEMPORAL_NIGHT_TZ_OFFSET", 3)
    NIGHT_START_HOUR = _int("TEMPORAL_NIGHT_START_HOUR", 0)
    NIGHT_END_HOUR = _int("TEMPORAL_NIGHT_END_HOUR", 6)
    CLUSTER_WINDOW_MIN = _int("TEMPORAL_CLUSTER_WINDOW_MIN", 60)
    BURST_MIN_PLATFORMS = _int("TEMPORAL_BURST_MIN_PLATFORMS", 3)
    BURST_MED_PLATFORMS = _int("TEMPORAL_BURST_MED_PLATFORMS", 5)
    BURST_HIGH_PLATFORMS = _int("TEMPORAL_BURST_HIGH_PLATFORMS", 8)
    NIGHT_LOW_EVENTS = _int("TEMPORAL_NIGHT_LOW_EVENTS", 2)
    NIGHT_MED_EVENTS = _int("TEMPORAL_NIGHT_MED_EVENTS", 5)
    NIGHT_HIGH_EVENTS = _int("TEMPORAL_NIGHT_HIGH_EVENTS", 10)
    SILENCE_DAYS = _int("TEMPORAL_SILENCE_DAYS", 180)
    BREACH_OVERLAP_DAYS = _int("TEMPORAL_BREACH_OVERLAP_DAYS", 30)


# Initialise on import
reload()
