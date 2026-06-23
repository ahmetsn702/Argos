from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional
from pathlib import Path
import os

def as_bool(v: str, default: bool = False) -> bool:
    if v is None: return default
    return str(v).strip().lower() in ("1", "true", "yes", "on")

class Settings(BaseSettings):
    # API Keys
    HIBP_KEY: Optional[str] = None
    GOOGLE_API_KEY: Optional[str] = None
    GOOGLE_CSE_API_KEY: Optional[str] = None
    GOOGLE_CSE_CX: Optional[str] = None
    NUMVERIFY_KEY: Optional[str] = None
    NUMLOOKUP_KEY: Optional[str] = None
    LEAKCHECK_KEY: Optional[str] = None
    SHODAN_KEY: Optional[str] = None
    ABSTRACT_EMAIL_KEY: Optional[str] = None
    ABSTRACT_PHONE_KEY: Optional[str] = None
    ABSTRACT_IP_KEY: Optional[str] = None
    SAUCENAO_API_KEY: Optional[str] = None
    MALTEGO_API_KEY: Optional[str] = None
    RAPIDAPI_KEY: Optional[str] = None
    VERIPHONE_KEY: Optional[str] = None
    TINEYE_KEY: Optional[str] = None

    
    # HIBP
    HIBP_ENABLED: bool = True
    HIBP_USER_AGENT: str = "ARGOS-OSINT/4.0"
    
    # Instagram
    IG_SESSIONID: Optional[str] = None
    IG_USER_AGENT: str = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
    IG_RETRY_MAX: int = 4
    IG_RETRY_BACKOFF_MS: int = 800
    IG_PW_TIMEOUT_MS: int = 10000
    
    # LinkedIn
    LI_AT: Optional[str] = None
    
    # General
    REQUEST_TIMEOUT: int = 20
    HEADLESS_MODE: bool = False
    USE_SYSTEM_CHROME: bool = False
    LINKEDIN_CACHE_TTL: int = 600
    USE_X_PLAYWRIGHT: bool = True
    X_PLAYWRIGHT_TIMEOUT: int = 30000
    MOBILE_SAFARI_UA: str = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    
    # AI
    OLLAMA_API_URL: str = "http://127.0.0.1:11434/api/generate"
    OLLAMA_MODEL: str = "phi3:mini"
    
    # Cache
    REDIS_URL: Optional[str] = None
    CACHE_TTL: int = 300

    # Confidence Graph
    CONFIDENCE_WEIGHT_OVERRIDES: Optional[str] = None
    CONFIDENCE_TTL_HOURS: int = 24
    CONFIDENCE_AGING_RATE: float = 0.95
    CONFIDENCE_CACHE_BACKEND: str = "memory"

    # Search
    SAFE_SEARCH: str = "off"
    LOCALE: str = "tr"
    
    # Graph DB (v5)
    NEO4J_URI: str = "bolt://localhost:7687"
    NEO4J_USER: str = "neo4j"
    NEO4J_PASSWORD: str = "changeme"
    GRAPH_DB_ENABLED: bool = False

    # Watchlist (v5)
    WATCHLIST_DB_PATH: str = "data/watchlist.db"
    ARCHIVE_BACKEND: str = "local"
    ARCHIVE_LOCAL_PATH: str = "data/archives"

    # Agent (v5)
    AGENT_DAILY_TOOL_QUOTA: int = 200
    AGENT_SESSION_MAX_TOOL_CALLS: int = 15
    AGENT_DAILY_BUDGET_USD: float = 5.0
    AGENT_TOOL_WHITELIST: str = (
        "email_osint,phone_lookup,social_scan,domain_lookup,"
        "confidence_build,temporal_analyze,pivot_run"
    )

    # RAG (v5)
    CHROMA_PERSIST_DIR: str = "data/chroma"

    model_config = SettingsConfigDict(
        env_file=str(Path(__file__).resolve().parents[2] / ".env"),
        env_file_encoding="utf-8",
        extra="ignore"
    )

# Settings instance
settings = Settings()

# Backward compatibility - mevcut kod için
API_KEY = settings.GOOGLE_CSE_API_KEY
CX = settings.GOOGLE_CSE_CX
SAFE = settings.SAFE_SEARCH
LOCALE = settings.LOCALE
IG_SESSIONID = settings.IG_SESSIONID
IG_USER_AGENT = settings.IG_USER_AGENT
IG_RETRY_MAX = settings.IG_RETRY_MAX
IG_RETRY_BACKOFF_MS = settings.IG_RETRY_BACKOFF_MS
REQUEST_TIMEOUT = settings.REQUEST_TIMEOUT
LI_AT = settings.LI_AT
HEADLESS_MODE = settings.HEADLESS_MODE
USE_SYSTEM_CHROME = settings.USE_SYSTEM_CHROME
LINKEDIN_CACHE_TTL = settings.LINKEDIN_CACHE_TTL
USE_X_PLAYWRIGHT = settings.USE_X_PLAYWRIGHT
X_PLAYWRIGHT_TIMEOUT = settings.X_PLAYWRIGHT_TIMEOUT
MOBILE_SAFARI_UA = settings.MOBILE_SAFARI_UA
OLLAMA_API_URL = settings.OLLAMA_API_URL
OLLAMA_MODEL = settings.OLLAMA_MODEL
