import asyncio
import logging
import re
from datetime import datetime
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from fastapi import FastAPI

from app.core.feature_flags import WATCHLIST_ENABLED
from app.core.config import settings
from app.repositories.watchlist_repo import WatchlistRepository
from app.services.watchlist.worker import process_target

logger = logging.getLogger("argos.watchlist.scheduler")

# Try to import redis
try:
    import redis.asyncio as redis
    REDIS_AVAILABLE = True
except ImportError:
    try:
        import aioredis as redis
        REDIS_AVAILABLE = True
    except ImportError:
        redis = None
        REDIS_AVAILABLE = False

_local_locks = set()
_scheduler_task = None
_running = False

class WatchlistLock:
    def __init__(self, target_id: int):
        self.target_id = target_id
        self.lock_key = f"watchlist:lock:{target_id}"
        self.redis_client = None
        self._acquired = False

    async def acquire(self) -> bool:
        if REDIS_AVAILABLE and settings.REDIS_URL:
            try:
                self.redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)
                res = await self.redis_client.set(self.lock_key, "1", ex=300, nx=True)
                if res:
                    self._acquired = True
                    return True
                return False
            except Exception as e:
                logger.warning("Redis lock acquisition failed, falling back to local lock: %s", e)
                
        # Local lock fallback
        if self.target_id in _local_locks:
            return False
        _local_locks.add(self.target_id)
        self._acquired = True
        return True

    async def release(self) -> None:
        if not self._acquired:
            return
        if REDIS_AVAILABLE and self.redis_client:
            try:
                await self.redis_client.delete(self.lock_key)
                await self.redis_client.close()
            except Exception:
                pass
        _local_locks.discard(self.target_id)
        self._acquired = False

def get_target_interval(target) -> float:
    """
    Get the interval for a target. Checks description for 'interval: X' or 'interval=X' in seconds.
    Defaults to 3600.0 seconds.
    """
    if target.description:
        match = re.search(r"interval[:=]\s*(\d+)", target.description, re.IGNORECASE)
        if match:
            return float(match.group(1))
    return 3600.0

async def scheduler_loop():
    """
    Background scheduler loop that runs checks every few seconds.
    """
    global _running
    logger.info("Watchlist periodic scheduler loop starting...")
    _running = True
    
    repo = WatchlistRepository()
    await repo.init_db()
    
    while _running:
        try:
            # Only process if watchlist feature flag is enabled
            if not WATCHLIST_ENABLED:
                await asyncio.sleep(5)
                continue
                
            targets = await repo.get_targets()
            active_targets = [t for t in targets if t.status == "active"]
            
            now = datetime.utcnow()
            for target in active_targets:
                if not _running:
                    break
                    
                interval = get_target_interval(target)
                is_due = False
                
                if not target.last_run:
                    is_due = True
                else:
                    try:
                        last_run_dt = datetime.fromisoformat(target.last_run)
                        elapsed = (now - last_run_dt).total_seconds()
                        if elapsed >= interval:
                            is_due = True
                    except Exception as e:
                        logger.error("Failed to parse last_run '%s' for target %s: %s", target.last_run, target.id, e)
                        is_due = True
                
                if is_due:
                    # Attempt to lock target
                    lock = WatchlistLock(target.id)
                    if await lock.acquire():
                        # Spawn background task to process target
                        asyncio.create_task(run_worker_with_lock(target.id, lock))
                        
        except Exception as e:
            logger.error("Error in watchlist scheduler loop: %s", e, exc_info=True)
            
        # Sleep for a small polling interval
        for _ in range(5):
            if not _running:
                break
            await asyncio.sleep(1)

async def run_worker_with_lock(target_id: int, lock: WatchlistLock):
    try:
        logger.info("Running scan worker for target %d", target_id)
        await process_target(target_id)
    except Exception as e:
        logger.error("Error processing target %d in scheduler task: %s", target_id, e, exc_info=True)
    finally:
        await lock.release()

@asynccontextmanager
async def watchlist_scheduler_lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    FastAPI lifespan context manager for the watchlist scheduler.
    Starts the scheduler loop on startup if WATCHLIST_ENABLED is True, and terminates on shutdown.
    """
    global _scheduler_task, _running
    
    if WATCHLIST_ENABLED:
        logger.info("Watchlist is enabled. Starting watchlist scheduler background task.")
        _scheduler_task = asyncio.create_task(scheduler_loop())
    else:
        logger.info("Watchlist is disabled. Scheduler background task will not be started.")
        
    yield
    
    if _scheduler_task:
        logger.info("Stopping watchlist scheduler background task...")
        _running = False
        _scheduler_task.cancel()
        try:
            await _scheduler_task
        except asyncio.CancelledError:
            pass
        logger.info("Watchlist scheduler background task stopped.")
