from typing import List
from app.services.storage.base import StorageAdapter

try:
    import boto3
except ImportError:
    boto3 = None


class S3Adapter(StorageAdapter):
    """
    S3 implementation of StorageAdapter (Stub).
    """

    def __init__(self, bucket_name: str = "argos-archives"):
        self.bucket_name = bucket_name
        self.client = None
        if boto3 is not None:
            pass

    async def save(self, key: str, data: bytes) -> str:
        raise NotImplementedError("S3Adapter save is not implemented.")

    async def load(self, key: str) -> bytes:
        raise NotImplementedError("S3Adapter load is not implemented.")

    async def delete(self, key: str) -> None:
        raise NotImplementedError("S3Adapter delete is not implemented.")

    async def list(self, prefix: str = "") -> List[str]:
        raise NotImplementedError("S3Adapter list is not implemented.")
