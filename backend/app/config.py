from pathlib import Path
import os

from dotenv import load_dotenv

BACKEND_DIR = Path(__file__).resolve().parents[1]
load_dotenv(BACKEND_DIR / ".env")
_configured_database_url = os.getenv("HYDROGUARD_DATABASE_URL")
_workspace_database_url = os.getenv("DATABASE_URL")
_database_url = _configured_database_url or (
    _workspace_database_url
    if _workspace_database_url and _workspace_database_url.startswith("sqlite:///")
    else "sqlite:///./hydroguard.db"
)
if not _database_url.startswith("sqlite:///"):
    raise RuntimeError("HydroGuard is configured for SQLite; set HYDROGUARD_DATABASE_URL to a SQLite URL.")
if _database_url.startswith("sqlite:///"):
    _sqlite_path = Path(_database_url.removeprefix("sqlite:///"))
    if not _sqlite_path.is_absolute():
        _database_url = f"sqlite:///{(BACKEND_DIR / _sqlite_path).resolve()}"
DATABASE_URL = _database_url
JWT_SECRET = os.getenv("JWT_SECRET") or os.getenv("SESSION_SECRET") or "hydroguard-secure-dev-secret-key-at-least-32-chars-long-2026"
JWT_ALGORITHM = "HS256"
JWT_EXPIRE_MINUTES = int(os.getenv("JWT_EXPIRE_MINUTES", "720"))
ASSUMED_MANUAL_DELAY_MINUTES = int(os.getenv("ASSUMED_MANUAL_DELAY_MINUTES", "360"))

raw_origins = os.getenv("CORS_ORIGINS", "*")
CORS_ORIGINS = ["*"] if raw_origins.strip() == "*" else [
    origin.strip() for origin in raw_origins.split(",") if origin.strip()
]


def database_path() -> Path | None:
    """Return a resolved SQLite path so the database stays in backend/."""
    if not DATABASE_URL.startswith("sqlite:///"):
        return None
    return Path(DATABASE_URL.removeprefix("sqlite:///"))