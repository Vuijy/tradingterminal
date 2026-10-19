import asyncio

from app.services.cache import TTLCache


def test_hit_and_expiry() -> None:
    c = TTLCache()
    c.set("k", 1, ttl=60)
    assert c.get("k") == (True, 1)
    c.set("k", 2, ttl=-1)  # already expired
    assert c.get("k") == (False, None)


def test_none_is_cached_briefly() -> None:
    c = TTLCache(none_ttl=0)
    c.set("k", None, ttl=3600)
    assert c.get("k") == (False, None)


def test_get_or_set_calls_factory_once_under_concurrency() -> None:
    c = TTLCache()
    calls = 0

    async def factory() -> str:
        nonlocal calls
        calls += 1
        await asyncio.sleep(0.01)
        return "value"

    async def run() -> list[str]:
        return await asyncio.gather(*(c.get_or_set("k", 60, factory) for _ in range(5)))

    results = asyncio.run(run())
    assert results == ["value"] * 5
    assert calls == 1


def test_get_or_set_survives_a_new_event_loop() -> None:
    c = TTLCache()

    async def once() -> int:
        return await c.get_or_set("k", -1, _const(1))  # ttl -1 -> never served from cache

    assert asyncio.run(once()) == 1
    assert asyncio.run(once()) == 1  # second loop reuses the key without blowing up


def _const(value: int):
    async def factory() -> int:
        return value

    return factory
