import logging
from app.services.watchlist.notifiers.base import NotifierBase
from app.models.watchlist import WatchlistAlert

logger = logging.getLogger("argos.watchlist.notifier")

class LogNotifier(NotifierBase):
    async def notify(self, alert: WatchlistAlert) -> None:
        """
        Log the alert to the Python logger.
        """
        logger.info(
            "Watchlist Alert [%s] Target ID %d (Severity: %s): %s - %s",
            alert.timestamp,
            alert.target_id,
            alert.severity,
            alert.title,
            alert.message
        )
