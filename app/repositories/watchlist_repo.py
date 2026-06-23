import os
import aiosqlite
from datetime import datetime
from typing import List, Optional
from app.models.watchlist import WatchlistTarget, WatchlistChange, WatchlistAlert
from app.core.config import settings


class WatchlistRepository:
    def __init__(self, db_path: str = None):
        if db_path is None:
            db_path = settings.WATCHLIST_DB_PATH
        self.db_path = db_path

    def _get_conn(self) -> aiosqlite.Connection:
        if self.db_path != ":memory:":
            dir_name = os.path.dirname(self.db_path)
            if dir_name:
                os.makedirs(dir_name, exist_ok=True)
        return aiosqlite.connect(self.db_path)

    async def init_db(self) -> None:
        async with self._get_conn() as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            await db.execute("""
                CREATE TABLE IF NOT EXISTS watchlist_targets (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    type TEXT NOT NULL,
                    value TEXT NOT NULL,
                    description TEXT,
                    status TEXT NOT NULL DEFAULT 'active',
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    last_run TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS watchlist_changes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id INTEGER NOT NULL,
                    change_type TEXT NOT NULL,
                    description TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    FOREIGN KEY (target_id) REFERENCES watchlist_targets (id) ON DELETE CASCADE
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS watchlist_alerts (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    target_id INTEGER NOT NULL,
                    title TEXT NOT NULL,
                    severity TEXT NOT NULL,
                    message TEXT NOT NULL,
                    timestamp TEXT NOT NULL,
                    is_read INTEGER NOT NULL DEFAULT 0,
                    FOREIGN KEY (target_id) REFERENCES watchlist_targets (id) ON DELETE CASCADE
                )
            """)
            await db.commit()

    async def create_target(self, target: WatchlistTarget) -> WatchlistTarget:
        now_str = datetime.utcnow().isoformat()
        created_at = target.created_at or now_str
        updated_at = target.updated_at or now_str

        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON;")
            cursor = await db.execute(
                """
                INSERT INTO watchlist_targets (type, value, description, status, created_at, updated_at, last_run)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (target.type, target.value, target.description, target.status, created_at, updated_at, target.last_run)
            )
            target_id = cursor.lastrowid

            # Log the change
            await db.execute(
                """
                INSERT INTO watchlist_changes (target_id, change_type, description, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (target_id, "created", f"Target created: {target.type} - {target.value}", now_str)
            )
            await db.commit()

            # Retrieve the created target
            async with db.execute("SELECT * FROM watchlist_targets WHERE id = ?", (target_id,)) as target_cursor:
                row = await target_cursor.fetchone()
                return WatchlistTarget(
                    id=row["id"],
                    type=row["type"],
                    value=row["value"],
                    description=row["description"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    last_run=row["last_run"]
                )

    async def get_targets(self) -> List[WatchlistTarget]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM watchlist_targets") as cursor:
                rows = await cursor.fetchall()
                return [
                    WatchlistTarget(
                        id=row["id"],
                        type=row["type"],
                        value=row["value"],
                        description=row["description"],
                        status=row["status"],
                        created_at=row["created_at"],
                        updated_at=row["updated_at"],
                        last_run=row["last_run"]
                    )
                    for row in rows
                ]

    async def get_target(self, target_id: int) -> Optional[WatchlistTarget]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM watchlist_targets WHERE id = ?", (target_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None
                return WatchlistTarget(
                    id=row["id"],
                    type=row["type"],
                    value=row["value"],
                    description=row["description"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    last_run=row["last_run"]
                )

    async def delete_target(self, target_id: int) -> bool:
        async with self._get_conn() as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            async with db.execute("SELECT 1 FROM watchlist_targets WHERE id = ?", (target_id,)) as cursor:
                if not await cursor.fetchone():
                    return False

            await db.execute("DELETE FROM watchlist_targets WHERE id = ?", (target_id,))
            await db.commit()
            return True

    async def update_target(self, target_id: int, updates: dict) -> Optional[WatchlistTarget]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON;")
            async with db.execute("SELECT * FROM watchlist_targets WHERE id = ?", (target_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

            now_str = datetime.utcnow().isoformat()

            # Build dynamic SQL update statement
            allowed_fields = {"type", "value", "description", "status", "last_run"}
            set_clauses = []
            values = []
            for field, val in updates.items():
                if field in allowed_fields:
                    set_clauses.append(f"{field} = ?")
                    values.append(val)

            if set_clauses:
                set_clauses.append("updated_at = ?")
                values.append(now_str)
                values.append(target_id)

                sql = f"UPDATE watchlist_targets SET {', '.join(set_clauses)} WHERE id = ?"
                await db.execute(sql, tuple(values))

                # Log change
                change_desc = f"Target updated: {', '.join(f'{k}={v}' for k, v in updates.items() if k in allowed_fields)}"
                await db.execute(
                    """
                    INSERT INTO watchlist_changes (target_id, change_type, description, timestamp)
                    VALUES (?, ?, ?, ?)
                    """,
                    (target_id, "updated", change_desc, now_str)
                )
                await db.commit()

            # Fetch updated target
            async with db.execute("SELECT * FROM watchlist_targets WHERE id = ?", (target_id,)) as cursor:
                row = await cursor.fetchone()
                return WatchlistTarget(
                    id=row["id"],
                    type=row["type"],
                    value=row["value"],
                    description=row["description"],
                    status=row["status"],
                    created_at=row["created_at"],
                    updated_at=row["updated_at"],
                    last_run=row["last_run"]
                )

    async def get_history(self, target_id: int) -> List[WatchlistChange]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            async with db.execute("SELECT * FROM watchlist_changes WHERE target_id = ? ORDER BY timestamp DESC", (target_id,)) as cursor:
                rows = await cursor.fetchall()
                return [
                    WatchlistChange(
                        id=row["id"],
                        target_id=row["target_id"],
                        change_type=row["change_type"],
                        description=row["description"],
                        timestamp=row["timestamp"]
                    )
                    for row in rows
                ]

    async def get_alerts(self, since: Optional[str] = None) -> List[WatchlistAlert]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            if since:
                sql = "SELECT * FROM watchlist_alerts WHERE timestamp >= ? ORDER BY timestamp DESC"
                params = (since,)
            else:
                sql = "SELECT * FROM watchlist_alerts ORDER BY timestamp DESC"
                params = ()

            async with db.execute(sql, params) as cursor:
                rows = await cursor.fetchall()
                return [
                    WatchlistAlert(
                        id=row["id"],
                        target_id=row["target_id"],
                        title=row["title"],
                        severity=row["severity"],
                        message=row["message"],
                        timestamp=row["timestamp"],
                        is_read=bool(row["is_read"])
                    )
                    for row in rows
                ]

    async def run_now(self, target_id: int) -> Optional[dict]:
        async with self._get_conn() as db:
            db.row_factory = aiosqlite.Row
            await db.execute("PRAGMA foreign_keys = ON;")
            async with db.execute("SELECT * FROM watchlist_targets WHERE id = ?", (target_id,)) as cursor:
                row = await cursor.fetchone()
                if not row:
                    return None

            now_str = datetime.utcnow().isoformat()

            # Update last_run
            await db.execute(
                "UPDATE watchlist_targets SET last_run = ?, updated_at = ? WHERE id = ?",
                (now_str, now_str, target_id)
            )

            # Log run
            await db.execute(
                """
                INSERT INTO watchlist_changes (target_id, change_type, description, timestamp)
                VALUES (?, ?, ?, ?)
                """,
                (target_id, "scan_run", "Scan triggered manually", now_str)
            )

            alerts_created = 0
            # If value contains "alert" (case insensitive), simulate creating an alert
            if "alert" in row["value"].lower():
                await db.execute(
                    """
                    INSERT INTO watchlist_alerts (target_id, title, severity, message, timestamp, is_read)
                    VALUES (?, ?, ?, ?, ?, 0)
                    """,
                    (target_id, "Simulated Alert", "high", f"Alert triggered for target value: {row['value']}", now_str)
                )
                alerts_created = 1

            await db.commit()
            return {
                "success": True,
                "target_id": target_id,
                "last_run": now_str,
                "alerts_created": alerts_created
            }

    async def create_alert(self, target_id: int, title: str, severity: str, message: str) -> WatchlistAlert:
        now_str = datetime.utcnow().isoformat()
        async with self._get_conn() as db:
            await db.execute("PRAGMA foreign_keys = ON;")
            cursor = await db.execute(
                """
                INSERT INTO watchlist_alerts (target_id, title, severity, message, timestamp, is_read)
                VALUES (?, ?, ?, ?, ?, 0)
                """,
                (target_id, title, severity, message, now_str)
            )
            alert_id = cursor.lastrowid
            await db.commit()
            return WatchlistAlert(
                id=alert_id,
                target_id=target_id,
                title=title,
                severity=severity,
                message=message,
                timestamp=now_str,
                is_read=False
            )
