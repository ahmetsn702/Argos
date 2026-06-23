import uuid

# In-memory storage to persist playbooks across requests
_store = {}

class PlaybookStorage:
    async def save(self, playbook: dict) -> str:
        # Generate new ID if not present in the playbook dictionary
        playbook_id = playbook.get("id") or str(uuid.uuid4())
        
        # Save a copy with the id field set
        stored_playbook = dict(playbook)
        stored_playbook["id"] = playbook_id
        _store[playbook_id] = stored_playbook
        return playbook_id

    async def get(self, id: str) -> dict | None:
        return _store.get(id)

    async def list_all(self) -> list[dict]:
        return list(_store.values())

    async def delete(self, id: str) -> bool:
        if id in _store:
            del _store[id]
            return True
        return False
