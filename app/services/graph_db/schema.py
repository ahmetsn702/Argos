"""Neo4j schema management — constraints and indexes.

All functions are async and idempotent (CREATE ... IF NOT EXISTS).
The Neo4j Python driver's session is synchronous; we wrap calls in
asyncio.to_thread to avoid blocking the event loop.
"""

import asyncio
from typing import Any, List


CONSTRAINTS: List[str] = [
    "CREATE CONSTRAINT IF NOT EXISTS FOR (f:Finding) REQUIRE f.id IS UNIQUE",
    "CREATE CONSTRAINT IF NOT EXISTS FOR (e:Entity) REQUIRE e.id IS UNIQUE",
]


INDEXES: List[str] = [
    "CREATE INDEX IF NOT EXISTS FOR (f:Finding) ON (f.type)",
    "CREATE INDEX IF NOT EXISTS FOR (f:Finding) ON (f.confidence)",
    "CREATE INDEX IF NOT EXISTS FOR (f:Finding) ON (f.created_at)",
    "CREATE INDEX IF NOT EXISTS FOR (e:Entity) ON (e.platform)",
]


async def create_constraints(driver: Any) -> None:
    """Apply uniqueness constraints. Safe to call repeatedly."""
    if driver is None:
        return

    def _run() -> None:
        with driver.session() as session:
            for stmt in CONSTRAINTS:
                session.run(stmt)

    await asyncio.to_thread(_run)


async def create_indexes(driver: Any) -> None:
    """Apply secondary indexes for hot lookup paths. Idempotent."""
    if driver is None:
        return

    def _run() -> None:
        with driver.session() as session:
            for stmt in INDEXES:
                session.run(stmt)

    await asyncio.to_thread(_run)


async def init_schema(driver: Any) -> None:
    """Initialize all schema objects (constraints + indexes)."""
    await create_constraints(driver)
    await create_indexes(driver)


__all__ = ["create_constraints", "create_indexes", "init_schema",
           "CONSTRAINTS", "INDEXES"]
