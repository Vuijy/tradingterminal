"""Shared test fixtures.

Real providers are swapped for in-memory fakes so the suite never touches the network.
New providers should follow the same pattern: test the HTTP layer against a fake, and
test the provider's parsing against small recorded fixtures.
"""

import datetime as dt
import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_fundamentals_provider, get_macro_provider, get_provider
from app.config import get_settings
from app.db.session import dispose_engines
from app.main import create_app
from app.models.company import Candle, CompanyProfile, NewsFeed, NewsItem, PriceHistory, Quote
from app.models.fundamentals import (
    ConceptMeta,
    Filing,
    FilingList,
    FinancialPeriod,
    Financials,
)
from app.models.macro import MacroObservation, MacroSeries
from app.services.cache import cache
from app.services.providers.base import FundamentalsProvider, MacroProvider, MarketDataProvider


class FakeProvider(MarketDataProvider):
    name = "fake"

    _profiles = {
        "AAPL": CompanyProfile(
            ticker="AAPL",
            name="Apple Inc.",
            exchange="NMS",
            currency="USD",
            sector="Technology",
            industry="Consumer Electronics",
            country="United States",
            market_cap=3.0e12,
            employees=160_000,
            source="fake",
        ),
    }

    async def get_profile(self, ticker: str) -> CompanyProfile | None:
        return self._profiles.get(ticker.upper())

    async def get_quote(self, ticker: str) -> Quote | None:
        if ticker.upper() not in self._profiles:
            return None
        return Quote(
            ticker=ticker.upper(),
            price=190.0,
            previous_close=188.0,
            change=2.0,
            change_pct=2.0 / 188.0 * 100,
            currency="USD",
            source="fake",
        )

    async def get_quotes(self, tickers: list[str]) -> list[Quote]:
        quotes = [await self.get_quote(t) for t in tickers]
        return [q for q in quotes if q is not None]

    async def get_history(self, ticker: str, range_: str, interval: str) -> PriceHistory | None:
        if ticker.upper() not in self._profiles:
            return None
        base = 1_700_000_000
        candles = [
            Candle(
                time=base + i * 86_400,
                open=100 + i,
                high=101 + i,
                low=99 + i,
                close=100.5 + i,
                volume=1e6,
            )
            for i in range(5)
        ]
        return PriceHistory(
            ticker=ticker.upper(),
            range=range_,
            interval=interval,
            currency="USD",
            timezone="America/New_York",
            candles=candles,
            source="fake",
        )

    async def get_news(self, ticker: str, limit: int) -> NewsFeed:
        items = [
            NewsItem(
                id=f"n{i}",
                title=f"Headline {i}",
                publisher="Fake Wire",
                url=f"https://example.com/{i}",
                published_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
                related_tickers=[ticker.upper()],
            )
            for i in range(min(limit, 3))
        ]
        return NewsFeed(ticker=ticker.upper(), items=items, source="fake")


class FakeFundamentals(FundamentalsProvider):
    name = "fake-edgar"

    async def get_financials(self, ticker: str) -> Financials | None:
        if ticker.upper() != "AAPL":
            return None
        concepts = [ConceptMeta(key="revenue", label="Revenue", kind="duration", unit="USD")]
        return Financials(
            ticker="AAPL",
            cik=320193,
            entity_name="Apple Inc.",
            concepts=concepts,
            annual=[
                FinancialPeriod(
                    period="FY2025",
                    fiscal_year=2025,
                    fiscal_period="FY",
                    start=dt.date(2024, 9, 29),
                    end=dt.date(2025, 9, 27),
                    values={"revenue": 416_161_000_000.0},
                )
            ],
            quarterly=[],
            source=self.name,
        )

    async def get_filings(
        self, ticker: str, forms: set[str] | None, limit: int
    ) -> FilingList | None:
        if ticker.upper() != "AAPL":
            return None
        filings = [
            Filing(
                accession="0000320193-25-000079",
                form="10-K",
                filed=dt.date(2025, 10, 31),
                report_date=dt.date(2025, 9, 27),
                url="https://www.sec.gov/Archives/edgar/data/320193/000032019325000079/aapl.htm",
            ),
            Filing(
                accession="0000320193-25-000050",
                form="8-K",
                filed=dt.date(2025, 7, 31),
                url="https://www.sec.gov/Archives/edgar/data/320193/000032019325000050/a8k.htm",
            ),
        ]
        if forms:
            filings = [f for f in filings if f.form in forms]
        return FilingList(ticker="AAPL", cik=320193, filings=filings[:limit], source=self.name)


class FakeMacro(MacroProvider):
    name = "fake-fred"

    async def get_series(self, series_id: str, start: dt.date | None = None) -> MacroSeries | None:
        sid = series_id.upper()
        if sid == "NOPE":
            return None
        today = dt.date.today()
        observations = [
            MacroObservation(date=today - dt.timedelta(days=365), value=4.0),
            MacroObservation(date=today - dt.timedelta(days=1), value=4.5),
            MacroObservation(date=today, value=5.0),
        ]
        if start:
            observations = [o for o in observations if o.date >= start]
        return MacroSeries(
            series_id=sid, title=sid, unit="%", observations=observations, source=self.name
        )


@pytest.fixture(scope="session", autouse=True)
def _test_database(tmp_path_factory: pytest.TempPathFactory) -> Iterator[None]:
    """Point the app at a throwaway SQLite file so tests never touch backend/data."""
    db_path = tmp_path_factory.mktemp("db") / "test.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path.as_posix()}"
    get_settings.cache_clear()
    yield
    dispose_engines()
    get_settings.cache_clear()


@pytest.fixture(autouse=True)
def _clear_cache() -> Iterator[None]:
    cache.clear()
    yield
    cache.clear()


@pytest.fixture
def client() -> Iterator[TestClient]:
    app = create_app()
    app.dependency_overrides[get_provider] = lambda: FakeProvider()
    app.dependency_overrides[get_fundamentals_provider] = lambda: FakeFundamentals()
    app.dependency_overrides[get_macro_provider] = lambda: FakeMacro()
    with TestClient(app) as c:
        yield c
