"""Cypher readonly guard — blocks write/DDL operations."""

FORBIDDEN_KEYWORDS = [
    "CREATE", "MERGE", "DELETE", "DETACH",
    "SET ", "REMOVE", "DROP", "CALL APOC.SCHEMA",
    "CALL DB.INDEX", "LOAD CSV", "FOREACH",
]


class CypherGuardError(Exception):
    """Raised when a query contains forbidden write keywords."""
    pass


def is_readonly_cypher(query: str) -> bool:
    """Return True if the query contains no write/DDL keywords."""
    upper = query.upper().strip()
    return not any(kw in upper for kw in FORBIDDEN_KEYWORDS)


def assert_readonly(query: str) -> None:
    """Raise CypherGuardError if the query is not read-only."""
    if not is_readonly_cypher(query):
        raise CypherGuardError(
            f"Write operations not allowed: {query[:80]}"
        )


__all__ = ["is_readonly_cypher", "assert_readonly", "CypherGuardError"]
