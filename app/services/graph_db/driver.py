"""Graph DB driver abstraction.

Singleton Neo4j driver with lazy connect. Returns None when feature flag
GRAPH_DB_ENABLED is false, so callers can fall back to in-memory paths
without exception handling.
"""

import threading
from typing import Any, Optional

from app.core.config import settings


_driver: Optional[Any] = None
_lock = threading.Lock()


def get_driver() -> Optional[Any]:
    """Return the Neo4j driver singleton, or None if disabled/unavailable.

    Behavior:
      - settings.GRAPH_DB_ENABLED is False -> None (no connect attempt).
      - neo4j package not installed       -> None (graceful degrade).
      - First successful call             -> creates and caches the driver.
      - Subsequent calls                  -> return the cached instance.
    """
    global _driver

    if not getattr(settings, "GRAPH_DB_ENABLED", False):
        return None

    if _driver is not None:
        return _driver

    with _lock:
        if _driver is not None:
            return _driver

        try:
            from neo4j import GraphDatabase
        except ImportError:
            return None

        _driver = GraphDatabase.driver(
            settings.NEO4J_URI,
            auth=(settings.NEO4J_USER, settings.NEO4J_PASSWORD),
        )
        return _driver


def close_driver() -> None:
    """Close the cached driver and reset state. Safe when no driver exists."""
    global _driver

    if _driver is None:
        return

    try:
        _driver.close()
    except Exception:
        # Best-effort close; never raise during shutdown.
        pass
    finally:
        _driver = None
