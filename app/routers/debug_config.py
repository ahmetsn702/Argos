from fastapi import APIRouter
from app.core.config import HEADLESS_MODE, USE_SYSTEM_CHROME, USE_X_PLAYWRIGHT, X_PLAYWRIGHT_TIMEOUT, MOBILE_SAFARI_UA
router = APIRouter(prefix="/debug", tags=["debug-config"])
@router.get("/config")
def debug_config():
    return {
        "HEADLESS_MODE": HEADLESS_MODE,
        "USE_SYSTEM_CHROME": USE_SYSTEM_CHROME,
        "USE_X_PLAYWRIGHT": USE_X_PLAYWRIGHT,
        "X_PLAYWRIGHT_TIMEOUT": X_PLAYWRIGHT_TIMEOUT,
        "UA_mobile_sample": MOBILE_SAFARI_UA[:42] + "..."
    }
