from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
import os, importlib

from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from app.core.limiter import limiter
from app.services.watchlist.scheduler import watchlist_scheduler_lifespan

app = FastAPI(title="ARGOS", version="4.0", description="ARGOS — Open Source Intelligence Platform", lifespan=watchlist_scheduler_lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8000", "http://127.0.0.1:8000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


class APIVersionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["X-API-Version"] = "4.0"
        response.headers["X-API-Name"] = "ARGOS-OSINT"
        return response


app.add_middleware(APIVersionMiddleware)

# Rate limiter (slowapi)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.abspath(os.path.join(BASE_DIR, ".."))

# UI Mounts (Hem /ui hem de /app/static/tester için)
ui_paths = ["ui", "app/static", "ui/stitch"]
for ui_path in ui_paths:
    UI_DIR = os.path.join(PROJECT_ROOT, ui_path)
    if os.path.isdir(UI_DIR):
        # /ui -> /ui/index.html
        # /app/static -> /app/static/tester/ui.html (varsayılan)
        mount_path = f"/{ui_path.split('/')[-1]}"
        if ui_path == "app/static":
             mount_path = "/static" # /app/static'i /static olarak bağla
        
        from fastapi.staticfiles import StaticFiles
        from fastapi.responses import FileResponse
        import time
        
        # Cache kontrolü için custom static files handler
        class NoCacheStaticFiles(StaticFiles):
            def file_response(self, *args, **kwargs):
                response = super().file_response(*args, **kwargs)
                response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"
                return response
        
        app.mount(mount_path, NoCacheStaticFiles(directory=UI_DIR, html=True), name=ui_path.split('/')[-1])
        print(f"[ok] mounted static UI: {mount_path} -> {UI_DIR}")

@app.get("/")
def root():
    # Yeni /mini paneli (eğer varsa) veya /ui (eski) öncelikli
    if os.path.exists(os.path.join(PROJECT_ROOT, "app/routers/mini_panel.py")):
        return RedirectResponse(url="/mini?mode=expert")
    if os.path.isdir(os.path.join(PROJECT_ROOT, "ui")):
        return RedirectResponse(url="/ui/")
    return {"ok": True, "msg": "API ayakta."}

@app.get("/__ping")
def __ping():
    return {"ok": True, "service": "argos", "version": "4.0"}

@app.get("/__routes")
def __routes():
    # Rotaları alfabetik olarak sırala
    return sorted([{"path": r.path, "name": r.name} for r in app.router.routes], key=lambda x: x["path"])

def _safe_include(module_name, attr="router"):
    try:
        # Tüm router'ların app.routers altında olduğunu varsayıyoruz
        mod = importlib.import_module(f"app.routers.{module_name}")
        router = getattr(mod, attr)
        app.include_router(router)
        print(f"[ok] mounted: app.routers.{module_name}")
    except Exception as e:
        print(f"[warn] skip app.routers.{module_name}: {e}")
        # traceback.print_exc() # Hata ayıklama için gerekirse aç

# --- Tüm Ana Router'ları Yükle ---
# (Loglardan ve son eklediklerimizden yola çıkarak)
routers_to_load = [
    "ai", "ai_gemma", "bios", "confidence",
    "composer", "correlation", "debug_config", "debug_instagram", "debug_x", 
    "facebook", "gemma_ui", 
    "geo_photo",
    "graph",
    "hunt_social_v2",
    "instagram",   # ← yeni birleşik IG router
    "linkedin_public",
    "llm_analysis",
    "media",
    "mini_panel",
    "darkweb",
    "domain",
    "face_search",
    "mosint_api",
    "phone",
    "pivot",
    "report",
    "photos", 
    "scan", 
    "search",
    "similarity",
    "temporal",
    "turkey_news",
    "turkey_mersis",
    "turkey_tc",
    "unified",
    "variants",
    "watchlist",
    "agent",
    "agent_ask",
    "playbook",
    "export",
    "maltego",
]

print("== Mounting routers ==")
for _m in sorted(list(set(routers_to_load))):
    _safe_include(_m)

print("== Application startup complete ==")