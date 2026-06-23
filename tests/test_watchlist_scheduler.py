import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from app.models.watchlist import WatchlistTarget
from app.services.watchlist.scheduler import (
    get_target_interval,
    WatchlistLock,
    watchlist_scheduler_lifespan,
    _local_locks
)
import app.services.watchlist.scheduler as scheduler_mod

def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro)

class DummyTarget:
    def __init__(self, description=None):
        self.description = description

def test_get_target_interval_default():
    assert get_target_interval(DummyTarget()) == 3600.0
    assert get_target_interval(DummyTarget("no interval here")) == 3600.0

def test_get_target_interval_custom():
    assert get_target_interval(DummyTarget("interval: 60")) == 60.0
    assert get_target_interval(DummyTarget("interval=120")) == 120.0
    assert get_target_interval(DummyTarget("some text interval:90 seconds")) == 90.0
    assert get_target_interval(DummyTarget("INTERVAL=15")) == 15.0

def test_watchlist_lock_local_fallback():
    _local_locks.clear()
    
    with patch("app.services.watchlist.scheduler.REDIS_AVAILABLE", False):
        lock1 = WatchlistLock(target_id=10)
        lock2 = WatchlistLock(target_id=10)
        lock3 = WatchlistLock(target_id=20)
        
        assert _run(lock1.acquire()) is True
        assert _run(lock2.acquire()) is False  # Lock for target 10 already acquired
        assert _run(lock3.acquire()) is True   # Lock for target 20 is free
        
        _run(lock1.release())
        assert _run(lock2.acquire()) is True   # Free now
        
        _run(lock2.release())
        _run(lock3.release())

def test_watchlist_lock_redis_success():
    _local_locks.clear()
    
    mock_redis_client = MagicMock()
    mock_redis_client.set = AsyncMock(return_value=True)
    mock_redis_client.delete = AsyncMock()
    mock_redis_client.close = AsyncMock()
    
    mock_redis_module = MagicMock()
    mock_redis_module.from_url = MagicMock(return_value=mock_redis_client)
    
    with patch("app.services.watchlist.scheduler.REDIS_AVAILABLE", True), \
         patch("app.services.watchlist.scheduler.settings") as mock_settings, \
         patch("app.services.watchlist.scheduler.redis", mock_redis_module):
        
        mock_settings.REDIS_URL = "redis://localhost:6379"
        lock = WatchlistLock(target_id=30)
        
        assert _run(lock.acquire()) is True
        mock_redis_client.set.assert_called_once_with("watchlist:lock:30", "1", ex=300, nx=True)
        
        _run(lock.release())
        mock_redis_client.delete.assert_called_once_with("watchlist:lock:30")
        mock_redis_client.close.assert_called_once()

def test_scheduler_loop_disabled():
    with patch("app.services.watchlist.scheduler.WATCHLIST_ENABLED", False), \
         patch("app.services.watchlist.scheduler.WatchlistRepository") as mock_repo_class:
        
        mock_repo = MagicMock()
        mock_repo.init_db = AsyncMock()
        mock_repo.get_targets = AsyncMock(return_value=[])
        mock_repo_class.return_value = mock_repo
        
        async def run_test():
            # Start loop in background
            task = asyncio.create_task(scheduler_mod.scheduler_loop())
            await asyncio.sleep(0.1)
            
            # Should not call get_targets since WATCHLIST_ENABLED is False
            mock_repo.get_targets.assert_not_called()
            
            scheduler_mod._running = False
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
                
        _run(run_test())

def test_scheduler_lifespan_flow():
    mock_app = MagicMock()
    
    with patch("app.services.watchlist.scheduler.WATCHLIST_ENABLED", True), \
         patch("app.services.watchlist.scheduler.scheduler_loop", AsyncMock()) as mock_loop:
        
        async def run_test():
            async with watchlist_scheduler_lifespan(mock_app):
                assert scheduler_mod._scheduler_task is not None
                assert not scheduler_mod._scheduler_task.done()
                
            assert scheduler_mod._scheduler_task.cancelled() or scheduler_mod._scheduler_task.done()
            
        _run(run_test())

def test_scheduler_loop_triggers_worker():
    _local_locks.clear()
    
    target = WatchlistTarget(
        id=1,
        type="email",
        value="test@example.com",
        description="interval: 5",
        status="active",
        created_at="2026-05-22T00:00:00",
        updated_at="2026-05-22T00:00:00",
        last_run=None
    )
    
    mock_repo = MagicMock()
    mock_repo.init_db = AsyncMock()
    mock_repo.get_targets = AsyncMock(return_value=[target])
    
    with patch("app.services.watchlist.scheduler.WATCHLIST_ENABLED", True), \
         patch("app.services.watchlist.scheduler.WatchlistRepository", return_value=mock_repo), \
         patch("app.services.watchlist.scheduler.process_target") as mock_process:
        
        mock_process.return_value = {"success": True}
        
        async def run_test():
            task = asyncio.create_task(scheduler_mod.scheduler_loop())
            await asyncio.sleep(0.5)
            
            scheduler_mod._running = False
            try:
                await asyncio.wait_for(task, timeout=1.0)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
                
            mock_process.assert_called_with(1)
            
        _run(run_test())
