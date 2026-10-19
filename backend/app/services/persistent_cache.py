"""SQLite-backed second level for the in-process TTL cache.

Used for payloads that are slow to fetch and change rarely (EDGAR companyfacts, the
ticker table, FRED series) so a restart does not mean re-downloading everything.
Values are stored as JSON; Pydantic models are tagged with their class so they come
back as models. All functions are synchronous and swallow storage errors: the cache
must never take the API down.
"""

from __future__ import annotations

import datetime as dt
import importlib
import json
import logging
import time
from typing import Any

from pydantic import BaseModel
from sqlalchemy import delete

from app.db.models import CacheEntry
from app.db.session import get_session_factory

log = logging.getLogger(__name__)

_PURGE_EVERY = 200
_writes = 0


def _model_ref(model: BaseModel) -> str:
    cls = type(model)
    return f"{cls.__module__}:{cls.__qualname__}"


def _load_model_class(ref: str) -> type[BaseModel]:
    module_name, _, qualname = ref.partition(":")
    if not module_name.startswith("app."):  # only our own schemas may be re-hydrated
        raise ValueError(f"refusing to load model outside app package: {ref}")
    cls = importlib.import_module(module_name)
    for part in qualname.split("."):
        cls = getattr(cls, part)
    if not (isinstance(cls, type) and issubclass(cls, BaseModel)):
        raise ValueError(f"not a pydantic model: {ref}")
    return cls


def encode(value: Any) -> str:
    if isinstance(value, BaseModel):
        return json.dumps({"model": _model_ref(value), "data": value.model_dump(mode="json")})
    if isinstance(value, list) and value and all(isinstance(v, BaseModel) for v in value):
        return json.dumps(
            {"models": _model_ref(value[0]), "data": [v.model_dump(mode="json") for v in value]}
        )
    return json.dumps({"data": value})


def decode(text: str) -> Any:
    payload = json.loads(text)
    if "model" in payload:
        return _load_model_class(payload["model"]).model_validate(payload["data"])
    if "models" in payload:
        cls = _load_model_class(payload["models"])
        return [cls.model_validate(d) for d in payload["data"]]
    return payload["data"]


def load(key: str) -> tuple[bool, Any, float]:
    """Return (found, value, remaining_ttl_seconds)."""
    try:
        with get_session_factory()() as db:
            row = db.get(CacheEntry, key)
            if row is None:
                return False, None, 0.0
            remaining = row.expires_at - time.time()
            if remaining <= 0:
                db.delete(row)
                db.commit()
                return False, None, 0.0
            return True, decode(row.value), remaining
    except Exception as exc:  # missing table, corrupt row, locked file: behave like a miss
        log.debug("persistent cache load failed for %s: %s", key, exc)
        return False, None, 0.0


def store(key: str, value: Any, ttl: float) -> None:
    global _writes
    try:
        text = encode(value)
        now = time.time()
        with get_session_factory()() as db:
            row = db.get(CacheEntry, key)
            if row is None:
                db.add(
                    CacheEntry(
                        key=key,
                        value=text,
                        expires_at=now + ttl,
                        updated_at=dt.datetime.now(dt.UTC),
                    )
                )
            else:
                row.value = text
                row.expires_at = now + ttl
                row.updated_at = dt.datetime.now(dt.UTC)
            _writes += 1
            if _writes % _PURGE_EVERY == 0:
                db.execute(delete(CacheEntry).where(CacheEntry.expires_at <= now))
            db.commit()
    except Exception as exc:
        log.debug("persistent cache store failed for %s: %s", key, exc)
