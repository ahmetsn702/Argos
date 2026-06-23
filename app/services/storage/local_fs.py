import os
from pathlib import Path
from typing import List
import anyio
from app.services.storage.base import StorageAdapter
from app.core.config import settings


class LocalFSAdapter(StorageAdapter):
    """
    Local File System implementation of StorageAdapter.
    Files are stored relative to a root directory.
    Uses scheme 'local://'.
    """

    def __init__(self, root_dir: str = None):
        if root_dir is None:
            root_dir = settings.ARCHIVE_LOCAL_PATH
        self.root_dir = os.path.abspath(root_dir)
        os.makedirs(self.root_dir, exist_ok=True)

    def _resolve(self, key: str) -> str:
        clean_key = key
        if clean_key.startswith("local://"):
            clean_key = clean_key[len("local://"):]

        base = Path(self.root_dir).resolve()
        target = (base / clean_key).resolve()

        # Path traversal protection
        try:
            common = os.path.commonpath([str(base), str(target)])
            if os.path.abspath(common) != os.path.abspath(base):
                raise ValueError(f"Path traversal attempt detected: {key}")
        except ValueError:
            raise ValueError(f"Path traversal attempt detected: {key}")

        return str(target)

    def _get_key_from_path(self, path: str) -> str:
        rel = os.path.relpath(path, self.root_dir)
        rel_uri = rel.replace("\\", "/")
        return f"local://{rel_uri}"

    async def save(self, key: str, data: bytes) -> str:
        target_path = self._resolve(key)

        def _write():
            os.makedirs(os.path.dirname(target_path), exist_ok=True)
            with open(target_path, "wb") as f:
                f.write(data)

        await anyio.to_thread.run_sync(_write)
        return self._get_key_from_path(target_path)

    async def load(self, key: str) -> bytes:
        target_path = self._resolve(key)

        def _read():
            if not os.path.exists(target_path):
                raise FileNotFoundError(f"File not found: {key}")
            with open(target_path, "rb") as f:
                return f.read()

        return await anyio.to_thread.run_sync(_read)

    async def delete(self, key: str) -> None:
        target_path = self._resolve(key)

        def _remove():
            if not os.path.exists(target_path):
                raise FileNotFoundError(f"File not found: {key}")
            os.remove(target_path)

        await anyio.to_thread.run_sync(_remove)

    async def list(self, prefix: str = "") -> List[str]:
        clean_prefix = prefix
        if clean_prefix.startswith("local://"):
            clean_prefix = clean_prefix[len("local://"):]

        # Path traversal protection for prefix
        if clean_prefix:
            base = Path(self.root_dir).resolve()
            target = (base / clean_prefix).resolve()
            try:
                common = os.path.commonpath([str(base), str(target)])
                if os.path.abspath(common) != os.path.abspath(base) and not str(target).startswith(str(base)):
                    raise ValueError(f"Path traversal attempt detected in prefix: {prefix}")
            except ValueError:
                raise ValueError(f"Path traversal attempt detected in prefix: {prefix}")

        def _list_sync():
            results = []
            for root, _, files in os.walk(self.root_dir):
                for file in files:
                    full_path = os.path.join(root, file)
                    rel = os.path.relpath(full_path, self.root_dir)
                    rel_uri = rel.replace("\\", "/")
                    if rel_uri.startswith(clean_prefix):
                        results.append(f"local://{rel_uri}")
            return results

        return await anyio.to_thread.run_sync(_list_sync)
