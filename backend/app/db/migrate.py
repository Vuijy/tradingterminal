"""Run Alembic migrations programmatically (used at app startup and in tests)."""

from pathlib import Path

from alembic import command
from alembic.config import Config

from app.config import BACKEND_DIR, get_settings

ALEMBIC_INI = BACKEND_DIR / "alembic.ini"


def alembic_config(url: str | None = None) -> Config:
    url = url or get_settings().database_url
    config = Config(str(ALEMBIC_INI))
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    config.set_main_option("sqlalchemy.url", url.replace("%", "%%"))
    return config


def run_migrations(url: str | None = None) -> None:
    """Upgrade the database at `url` (default: settings) to the latest revision."""
    url = url or get_settings().database_url
    if url.startswith("sqlite:///"):
        path = url.removeprefix("sqlite:///")
        if path and path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
    command.upgrade(alembic_config(url), "head")
