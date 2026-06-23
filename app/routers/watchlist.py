from fastapi import APIRouter, Depends, HTTPException
from typing import Any, Optional
from app.models.watchlist import WatchlistTarget
from app.repositories.watchlist_repo import WatchlistRepository
from app.core.feature_flags import WATCHLIST_ENABLED

router = APIRouter(prefix="/watchlist", tags=["watchlist"])


async def get_repo() -> WatchlistRepository:
    repo = WatchlistRepository()
    await repo.init_db()
    return repo


@router.post("/targets")
async def create_target(
    target: WatchlistTarget, repo: WatchlistRepository = Depends(get_repo)
) -> Any:
    if not WATCHLIST_ENABLED:
        return {"enabled": False}
    try:
        new_target = await repo.create_target(target)
        return new_target
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/targets")
async def get_targets(repo: WatchlistRepository = Depends(get_repo)) -> Any:
    if not WATCHLIST_ENABLED:
        return {"enabled": False}
    return await repo.get_targets()


@router.delete("/targets/{id}")
async def delete_target(
    id: int, repo: WatchlistRepository = Depends(get_repo)
) -> Any:
    if not WATCHLIST_ENABLED:
        return {"enabled": False}
    deleted = await repo.delete_target(id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Target not found")
    return {"success": True}


@router.put("/targets/{id}")
async def update_target(
    id: int, target_update: dict, repo: WatchlistRepository = Depends(get_repo)
) -> Any:
    if not WATCHLIST_ENABLED:
        return {"enabled": False}
    updated = await repo.update_target(id, target_update)
    if not updated:
        raise HTTPException(status_code=404, detail="Target not found")
    return updated


@router.get("/targets/{id}/history")
async def get_history(
    id: int, repo: WatchlistRepository = Depends(get_repo)
) -> Any:
    if not WATCHLIST_ENABLED:
        return {"enabled": False}
    history = await repo.get_history(id)
    return history


@router.get("/alerts")
async def get_alerts(
    since: Optional[str] = None, repo: WatchlistRepository = Depends(get_repo)
) -> Any:
    if not WATCHLIST_ENABLED:
        return {"enabled": False}
    return await repo.get_alerts(since=since)


@router.post("/targets/{id}/run-now")
async def run_now(
    id: int, repo: WatchlistRepository = Depends(get_repo)
) -> Any:
    if not WATCHLIST_ENABLED:
        return {"enabled": False}
    res = await repo.run_now(id)
    if not res:
        raise HTTPException(status_code=404, detail="Target not found")
    return res
