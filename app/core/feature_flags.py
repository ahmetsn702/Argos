import os


def _bool(key: str, default: bool = False) -> bool:
    return os.getenv(key, str(default)).strip().lower() in ("1", "true", "yes", "on")


GRAPH_DB_ENABLED: bool = _bool("GRAPH_DB_ENABLED", False)
WATCHLIST_ENABLED: bool = _bool("WATCHLIST_ENABLED", False)
AGENT_ENABLED: bool = _bool("AGENT_ENABLED", False)
MALTEGO_ENABLED: bool = _bool("MALTEGO_ENABLED", False)
