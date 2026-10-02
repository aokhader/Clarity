"""Central configuration. Everything comes from environment variables or .env."""
import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

CLIO_BASE_URL = os.getenv("CLIO_BASE_URL", "https://app.clio.com").rstrip("/")
CLIO_API_URL = f"{CLIO_BASE_URL}/api/v4"
CLIO_CLIENT_ID = os.getenv("CLIO_CLIENT_ID", "")
CLIO_CLIENT_SECRET = os.getenv("CLIO_CLIENT_SECRET", "")
CLIO_REDIRECT_URI = os.getenv("CLIO_REDIRECT_URI", "http://127.0.0.1:8765/callback")
CLIO_ACCESS_TOKEN = os.getenv("CLIO_ACCESS_TOKEN", "")
CLIO_MATTER_ID = os.getenv("CLIO_MATTER_ID", "")  # set by `python -m backend.connect`

TOKEN_FILE = Path(os.getenv("CLIO_TOKEN_FILE", ROOT / ".clio_token.json"))
DATA_DIR = Path(os.getenv("DATA_DIR", ROOT / "data"))
DB_PATH = Path(os.getenv("DB_PATH", DATA_DIR / "case.db"))
DOCS_DIR = DATA_DIR / "documents"

PAGE_LIMIT = 200  # Clio's maximum page size
