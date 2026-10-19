"""SQLAlchemy engine/session management.

Engines are created lazily per database URL so tests can point at a temporary SQLite
file by setting DATABASE_URL before the app starts. Schema changes go through Alembic
(see app/db/migrate.py and backend/alembic/); never call Base.metadata.create_all.
"""

from collections.abc import Generator
from typing import Annotated

from fastapi import Depends
from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings


class Base(DeclarativeBase):
    """Declarative base for all ORM models (app/db/models.py)."""


_engines: dict[str, Engine] = {}


def get_engine(url: str | None = None) -> Engine:
    url = url or get_settings().database_url
    engine = _engines.get(url)
    if engine is None:
        connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
        engine = create_engine(url, connect_args=connect_args)
        _engines[url] = engine
    return engine


def get_session_factory(url: str | None = None) -> sessionmaker[Session]:
    return sessionmaker(bind=get_engine(url), autoflush=False, expire_on_commit=False)


def get_db() -> Generator[Session, None, None]:
    """FastAPI dependency yielding a request-scoped session."""
    db = get_session_factory()()
    try:
        yield db
    finally:
        db.close()


def dispose_engines() -> None:
    for engine in _engines.values():
        engine.dispose()
    _engines.clear()


DbDep = Annotated[Session, Depends(get_db)]
