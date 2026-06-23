import asyncio
from datetime import datetime
from typing import Dict, Any, Optional

from app.models.watchlist import WatchlistTarget, WatchlistAlert
from app.repositories.watchlist_repo import WatchlistRepository
from app.services.watchlist.snapshot import SnapshotService
from app.services.watchlist.diff import DiffEngine
from app.services.watchlist.archiver import WatchlistArchiver
from app.services.watchlist.notifiers.log_notifier import LogNotifier

# Scanning integrations
from app.services.hibp_service import hibp_breached_account
from app.services.scan_service import probe_single, PLATFORMS
from app.services.domain_service import domain_osint

async def fetch_target_data(target: WatchlistTarget) -> dict:
    """
    Fetch the latest data for the target.
    Returns a dict containing standard fields: confidence, platforms, breaches, temporal_anomaly.
    """
    target_type = target.type.lower()
    value = target.value
    
    # Initialize with default/fallback data structure
    data = {
        "confidence": 1.0,
        "platforms": [],
        "breaches": [],
        "temporal_anomaly": False
    }
    
    if target_type == "email":
        try:
            res = await hibp_breached_account(value)
            if res.get("ok") and res.get("data"):
                breaches = res["data"].get("breaches_list", [])
                data["breaches"] = breaches
                data["confidence"] = 0.9
        except Exception:
            pass
            
    elif target_type == "username":
        try:
            tasks = [probe_single(value, p) for p in PLATFORMS]
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            platforms_found = []
            for res in results:
                if isinstance(res, dict) and res.get("status") == "exists":
                    platforms_found.append(res.get("platform"))
            data["platforms"] = platforms_found
            data["confidence"] = 0.8
        except Exception:
            pass
            
    elif target_type == "domain" or target_type == "url":
        try:
            res = await domain_osint(value)
            if res.get("ip"):
                data["confidence"] = 0.95
            else:
                data["confidence"] = 0.5
        except Exception:
            pass
            
    return data

async def process_target(target_id: int) -> dict:
    """
    Orchestrates target monitoring scan execution:
    1. Fetches target data from active sources
    2. Takes a snapshot of the fetched data
    3. Compares with the previous snapshot (diff)
    4. Archives the details if changes are detected
    5. Inserts alert into DB and triggers notifications if severity/changes warrant it.
    6. Updates last_run timestamp for the target.
    """
    repo = WatchlistRepository()
    target = await repo.get_target(target_id)
    if not target:
        return {"success": False, "error": f"Target {target_id} not found"}
        
    if target.status != "active":
        return {"success": False, "message": f"Target {target_id} is not active"}

    # 1. Fetch latest data
    new_data = await fetch_target_data(target)
    
    # 2. Get latest snapshot from database
    snapshot_service = SnapshotService()
    old_snapshot = await snapshot_service.get_latest(target_id)
    
    # 3. Compare old and new data using DiffEngine
    diff_engine = DiffEngine()
    diff_result = diff_engine.compare(old_snapshot, new_data)
    
    changes = diff_result.get("changes", [])
    severity = diff_result.get("severity", "low")
    
    # 4. Take/save new snapshot
    new_snapshot = await snapshot_service.take_snapshot(target_id, new_data)
    
    archive_uri = None
    alert_created = False
    
    # Update target last_run timestamp
    now_str = datetime.utcnow().isoformat()
    await repo.update_target(target_id, {"last_run": now_str})
    
    if changes:
        # 5. Archive the state
        archive_data = dict(new_data)
        if target.type.lower() in ("domain", "url"):
            archive_data["url"] = target.value
            
        archiver = WatchlistArchiver()
        archive_uri = await archiver.archive(target_id, archive_data)
        
        # 6. Create Alert and Notify
        change_messages = [c.get("message") for c in changes if c.get("message")]
        alert_message = "; ".join(change_messages)
        alert_title = f"Watchlist Change for {target.type} - {target.value}"
        
        # Insert alert into DB
        alert = await repo.create_alert(
            target_id=target_id,
            title=alert_title,
            severity=severity,
            message=alert_message
        )
        alert_created = True
        
        # Trigger notifications
        notifier = LogNotifier()
        await notifier.notify(alert)
        
    return {
        "success": True,
        "target_id": target_id,
        "changes_detected": len(changes) > 0,
        "changes": changes,
        "severity": severity,
        "archive_uri": archive_uri,
        "alert_created": alert_created
    }
