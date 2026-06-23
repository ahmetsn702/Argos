import os
from typing import Optional
from app.services.storage.base import StorageAdapter
from app.services.storage.local_fs import LocalFSAdapter
from app.services.storage.s3 import S3Adapter
from app.core.config import settings

_adapter_cache = {}


def get_adapter(backend: Optional[str] = None) -> StorageAdapter:
    """
    Factory function to retrieve a cached singleton instance of the appropriate
    StorageAdapter based on the configured backend.
    """
    if backend is None:
        backend = os.getenv("ARCHIVE_BACKEND", settings.ARCHIVE_BACKEND)

    backend = backend.lower().strip()

    if backend == "local":
        if "local" not in _adapter_cache:
            _adapter_cache["local"] = LocalFSAdapter()
        return _adapter_cache["local"]
    elif backend == "s3":
        if "s3" not in _adapter_cache:
            _adapter_cache["s3"] = S3Adapter()
        return _adapter_cache["s3"]
    else:
        raise ValueError(f"Unsupported storage backend: {backend}")


# Alias matching the blueprint naming convention
get_storage_adapter = get_adapter
