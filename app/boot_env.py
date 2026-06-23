from app.utils import pw_safe
from pathlib import Path
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]  # ...\footprint-backend\app -> parents[1] = project root
# .env'i importlardan ÖNCE ve override=True ile yükle
load_dotenv(dotenv_path=ROOT / ".env", override=True, encoding="utf-8")