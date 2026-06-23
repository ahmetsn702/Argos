from abc import ABC, abstractmethod
from typing import List


class StorageAdapter(ABC):
    """
    Abstract Base Class defining the interface for storage backends.
    """

    @abstractmethod
    async def save(self, key: str, data: bytes) -> str:
        """
        Saves data under the given key/path.
        Returns the URI representing the saved resource (e.g. local://..., s3://...).
        """
        pass

    @abstractmethod
    async def load(self, key: str) -> bytes:
        """
        Loads and returns the data for the given key/URI.
        Raises FileNotFoundError if the file or key does not exist.
        """
        pass

    @abstractmethod
    async def delete(self, key: str) -> None:
        """
        Deletes the data at the given key/URI.
        Raises FileNotFoundError if the file or key does not exist.
        """
        pass

    @abstractmethod
    async def list(self, prefix: str = "") -> List[str]:
        """
        Lists all URIs matching the specified prefix.
        """
        pass
