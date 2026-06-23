from abc import ABC, abstractmethod
from app.models.watchlist import WatchlistAlert

class NotifierBase(ABC):
    @abstractmethod
    async def notify(self, alert: WatchlistAlert) -> None:
        """
        Send a notification for the given watchlist alert.
        """
        pass
