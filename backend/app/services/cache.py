"""Tiny in-process TTL cache with per-key single-flight and an optional SQLite second level.

Every data source this app uses is free and rate-limited, so repeated requests for the
same ticker must not reach the upstream. Single-flight means that when several panels
ask for the same key at once (profile and quote both need Yahoo's `info`), only one
upstream call is made and the others wait for it.

Pass `persist=True` for slow, rarely changing payloads (EDGAR facts, FRED series): on a
memory miss the value is looked up in SQLite (app/services/persistent_cache.py) before
the factory runs, and written there after. Everything else stays memory-only.

Good enough for one process. Swap for Redis if the app is ever run as several workers.
"""

import asyncio
import time
from collections.abc import Awaitable, Callable
from typing import Any

from app.services import persistent_cache

_PURGE_EVERY = 500


class TTLCache:
    def __init__(self, none_ttl: float = 30.0) -> None:
        # None usually means "unknown ticker" or a transient upstream hiccup; keep it briefly.
        self._none_ttl = none_ttl
        self._store: dict[str, tuple[float, Any]] = {}
        self._locks: dict[str, tuple[asyncio.AbstractEventLoop, asyncio.Lock]] = {}
        self._sets = 0

    def get(self, key: str) -> tuple[bool, Any]:
        hit = self._store.get(key)
        if hit is None:
            return False, None
        expires_at, value = hit
        if expires_at <= time.monotonic():
            self._store.pop(key, None)
            return False, None
        return True, value

    def set(self, key: str, value: Any, ttl: float) -> None:
        if value is None:
            ttl = min(ttl, self._none_ttl)
        self._store[key] = (time.monotonic() + ttl, value)
        self._sets += 1
        if self._sets % _PURGE_EVERY == 0:
            self._purge_expired()

    async def get_or_set(
        self,
        key: str,
        ttl: float,
        factory: Callable[[], Awaitable[Any]],
        *,
        persist: bool = False,
    ) -> Any:
        found, value = self.get(key)
        if found:
            return value
        async with self._lock_for(key):
            found, value = self.get(key)
            if found:
                return value
            if persist:
                found, value, remaining = await asyncio.to_thread(persistent_cache.load, key)
                if found:
                    self.set(key, value, min(ttl, remaining))
                    return value
            value = await factory()
            self.set(key, value, ttl)
            if persist and value is not None:
                await asyncio.to_thread(persistent_cache.store, key, value, ttl)
            return value

    def clear(self) -> None:
        self._store.clear()
        self._locks.clear()

    def _lock_for(self, key: str) -> asyncio.Lock:
        # asyncio.Lock binds to the loop that first uses it; the test suite spins up a
        # fresh loop per client, so rebuild the lock when the loop changed.
        loop = asyncio.get_running_loop()
        entry = self._locks.get(key)
        if entry is None or entry[0] is not loop:
            entry = (loop, asyncio.Lock())
            self._locks[key] = entry
        return entry[1]

    def _purge_expired(self) -> None:
        now = time.monotonic()
        for k in [k for k, (exp, _) in self._store.items() if exp <= now]:
            self._store.pop(k, None)


cache = TTLCache()
