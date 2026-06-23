"""CLI: Initialize Neo4j schema (constraints + indexes).

Usage:
    python scripts/init_graph_db.py

Requires GRAPH_DB_ENABLED=true and a reachable Neo4j instance configured
via NEO4J_URI / NEO4J_USER / NEO4J_PASSWORD in .env.
"""

import asyncio
import sys

from app.services.graph_db.driver import close_driver, get_driver
from app.services.graph_db.schema import init_schema


async def _main() -> int:
    driver = get_driver()
    if driver is None:
        print(
            "ERROR: Neo4j driver unavailable. "
            "Check GRAPH_DB_ENABLED, NEO4J_URI, and that the neo4j package is installed."
        )
        return 1

    try:
        await init_schema(driver)
    except Exception as exc:
        print(f"ERROR: Schema initialization failed: {exc}")
        return 1
    finally:
        close_driver()

    print("Schema initialized")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
