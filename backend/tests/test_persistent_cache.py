import asyncio
import datetime as dt

import pytest

from app.db.migrate import run_migrations
from app.models.macro import MacroObservation, MacroSeries
from app.services import persistent_cache
from app.services.cache import TTLCache


@pytest.fixture(autouse=True)
def _schema() -> None:
    run_migrations()  # against the throwaway DATABASE_URL set in conftest


def test_plain_json_survives_memory_clear() -> None:
    c = TTLCache()
    calls = 0

    async def factory() -> dict:
        nonlocal calls
        calls += 1
        return {"a": [1, 2], "b": "x"}

    assert asyncio.run(c.get_or_set("pc:plain", 60, factory, persist=True)) == {
        "a": [1, 2],
        "b": "x",
    }
    c.clear()

    async def must_not_run() -> dict:
        raise AssertionError("factory should not be called; value should come from SQLite")

    assert asyncio.run(c.get_or_set("pc:plain", 60, must_not_run, persist=True)) == {
        "a": [1, 2],
        "b": "x",
    }
    assert calls == 1


def test_pydantic_models_roundtrip() -> None:
    series = MacroSeries(
        series_id="DGS10",
        title="t",
        unit="%",
        observations=[MacroObservation(date=dt.date(2026, 1, 2), value=4.5)],
        source="fred",
    )
    persistent_cache.store("pc:model", series, ttl=60)
    found, value, remaining = persistent_cache.load("pc:model")
    assert found and isinstance(value, MacroSeries)
    assert value.observations[0].value == 4.5
    assert 0 < remaining <= 60

    persistent_cache.store("pc:list", [series, series], ttl=60)
    found, value, _ = persistent_cache.load("pc:list")
    assert found and len(value) == 2 and all(isinstance(v, MacroSeries) for v in value)


def test_expired_rows_are_misses() -> None:
    persistent_cache.store("pc:old", {"x": 1}, ttl=-5)
    assert persistent_cache.load("pc:old") == (False, None, 0.0)


def test_none_is_not_persisted() -> None:
    c = TTLCache()

    async def nothing() -> None:
        return None

    asyncio.run(c.get_or_set("pc:none", 60, nothing, persist=True))
    assert persistent_cache.load("pc:none")[0] is False


def test_refuses_foreign_model_refs() -> None:
    with pytest.raises(ValueError):
        persistent_cache.decode('{"model": "os:system", "data": {}}')
