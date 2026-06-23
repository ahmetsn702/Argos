import json
from datetime import datetime
from typing import Any, List, Optional
from app.services.storage.factory import get_storage_adapter


class SnapshotService:
    """
    Service responsible for storing and retrieving watchlist target snapshots.
    """

    def __init__(self, storage_adapter=None):
        self.storage = storage_adapter or get_storage_adapter()

    async def take_snapshot(self, target_id: Any, data: dict) -> dict:
        """
        Saves a snapshot of target data with a timestamp to the configured storage adapter.
        """
        timestamp = datetime.utcnow().isoformat()
        # Windows file system does not allow colons in filenames.
        # We replace colons with dashes in the filename part of the key.
        safe_timestamp = timestamp.replace(":", "-")
        key = f"watchlist/snapshots/{target_id}/{safe_timestamp}.json"

        snapshot = {
            "target_id": target_id,
            "timestamp": timestamp,
            "data": data
        }

        await self.storage.save(key, json.dumps(snapshot).encode("utf-8"))
        return snapshot

    async def list_snapshots(self, target_id: Any) -> List[dict]:
        """
        Lists all snapshots stored for a given target, sorted by timestamp ascending.
        """
        prefix = f"watchlist/snapshots/{target_id}/"
        try:
            uris = await self.storage.list(prefix=prefix)
        except Exception:
            return []

        snapshots = []
        for uri in uris:
            try:
                content_bytes = await self.storage.load(uri)
                snapshot = json.loads(content_bytes.decode("utf-8"))
                snapshots.append(snapshot)
            except Exception:
                pass

        snapshots.sort(key=lambda s: s.get("timestamp", ""))
        return snapshots

    async def get_latest(self, target_id: Any) -> Optional[dict]:
        """
        Retrieves the latest snapshot for a given target, or None if no snapshots exist.
        """
        snapshots = await self.list_snapshots(target_id)
        if not snapshots:
            return None
        return snapshots[-1]
