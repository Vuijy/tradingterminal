"""Application settings.

Values are read from environment variables, falling back to a `.env` file at the
repo root (and then `backend/.env`). Field names map to env vars case-insensitively,
e.g. `database_url` <- `DATABASE_URL`.
"""

from functools import lru_cache
from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(REPO_ROOT / ".env", BACKEND_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- App ---
    app_name: str = "Trading Terminal API"
    version: str = "0.1.0"
    app_env: str = "development"
    app_debug: bool = False
    api_host: str = "127.0.0.1"
    api_port: int = 8000
    api_prefix: str = "/api/v1"
    cors_origins: str = "http://localhost:5173,http://127.0.0.1:5173"

    # --- Storage ---
    data_dir: Path = BACKEND_DIR / "data"
    database_url: str = f"sqlite:///{(BACKEND_DIR / 'data' / 'terminal.db').as_posix()}"

    # --- Data providers (see docs/DATA_SOURCES.md) ---
    # Market data + news: yfinance (no key).
    # Fundamentals: SEC EDGAR. The SEC asks for a User-Agent naming the app and a contact.
    sec_edgar_user_agent: str = "TradingTerminal/0.1 (set SEC_EDGAR_USER_AGENT in .env)"
    # Macro: FRED. Optional; without a key the public CSV endpoint is used instead.
    fred_api_key: str = ""

    @property
    def cors_origins_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    """Cached settings instance. Call `get_settings.cache_clear()` in tests if needed."""
    return Settings()
