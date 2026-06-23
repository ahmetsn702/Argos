# tests/test_pivot_strategy_map.py
"""Tests for app/services/pivot/strategy_map.py."""

import asyncio

from app.models.confidence import FindingType
from app.services.pivot.strategy_map import STRATEGY_MAP, strategies_for


_REQUIRED_TYPES = {
    FindingType.EMAIL,
    FindingType.PHONE,
    FindingType.USERNAME,
    FindingType.DOMAIN,
    FindingType.IP,
    FindingType.NAME,
}


def test_strategy_map_covers_all_required_finding_types():
    """Every FindingType used by autonomous pivot has a registry entry."""
    for ftype in _REQUIRED_TYPES:
        assert ftype in STRATEGY_MAP, f"Missing strategy for {ftype}"


def test_strategy_map_each_required_list_non_empty():
    """Required FindingTypes have at least one expander registered."""
    for ftype in _REQUIRED_TYPES:
        strategies = STRATEGY_MAP[ftype]
        assert len(strategies) >= 1, f"No strategies for {ftype}"


def test_strategy_map_all_callables_are_async():
    """Every registered strategy is an async function."""
    for ftype, strategies in STRATEGY_MAP.items():
        for fn in strategies:
            assert asyncio.iscoroutinefunction(fn), (
                f"{ftype}: {fn} is not async"
            )


def test_strategies_for_helper_returns_copy():
    """strategies_for() returns a fresh list — caller mutations don't leak."""
    out = strategies_for(FindingType.EMAIL)
    out.append("dummy")
    assert "dummy" not in STRATEGY_MAP[FindingType.EMAIL]


def test_strategies_for_unknown_type_returns_empty():
    """Unregistered types get an empty list, not KeyError."""
    # LOCATION is registered but empty by design.
    assert strategies_for(FindingType.LOCATION) == []
