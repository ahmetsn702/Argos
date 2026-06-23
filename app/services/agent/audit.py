import os
import json
from datetime import datetime, timezone
import aiosqlite

class AuditLogger:
    def __init__(self, db_path: str = "data/agent_audit.db"):
        self.db_path = db_path
        self._initialized = False

    async def initialize(self):
        if self._initialized:
            return
        parent_dir = os.path.dirname(os.path.abspath(self.db_path))
        os.makedirs(parent_dir, exist_ok=True)
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS audit_logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT,
                    tool TEXT,
                    params TEXT,
                    result TEXT,
                    timestamp TEXT
                )
            """)
            await db.commit()
        self._initialized = True

    async def log_tool_call(self, session_id: str, tool: str, params: dict, result: dict):
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO audit_logs (session_id, tool, params, result, timestamp) VALUES (?, ?, ?, ?, ?)",
                (
                    session_id,
                    tool,
                    json.dumps(params),
                    json.dumps(result),
                    datetime.now(timezone.utc).isoformat()
                )
            )
            await db.commit()

    async def get_logs(self, session_id: str = None) -> list:
        await self.initialize()
        async with aiosqlite.connect(self.db_path) as db:
            if session_id:
                cursor = await db.execute(
                    "SELECT id, session_id, tool, params, result, timestamp FROM audit_logs WHERE session_id = ? ORDER BY id ASC",
                    (session_id,)
                )
            else:
                cursor = await db.execute(
                    "SELECT id, session_id, tool, params, result, timestamp FROM audit_logs ORDER BY id ASC"
                )
            rows = await cursor.fetchall()
            logs = []
            for r in rows:
                logs.append({
                    "id": r[0],
                    "session_id": r[1],
                    "tool": r[2],
                    "params": json.loads(r[3]),
                    "result": json.loads(r[4]),
                    "timestamp": r[5]
                })
            return logs
