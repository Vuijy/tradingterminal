"""Provider interfaces.

Every external data source is wrapped in a class implementing one of these interfaces
so the rest of the app never depends on a vendor's payload shape. Routes receive
providers through FastAPI dependencies (app/api/deps.py); tests inject fakes.

Sources (docs/DATA_SOURCES.md):
  - yfinance   -> MarketDataProvider  (profile, quote, OHLCV history, news)
  - SEC EDGAR  -> FundamentalsProvider (financial statements, filings)
  - FRED       -> MacroProvider        (macro time series)
"""

from abc import ABC, abstractmethod
from datetime import date

from app.models.company import CompanyProfile, NewsFeed, PriceHistory, Quote
from app.models.fundamentals import FilingList, Financials
from app.models.macro import MacroSeries


class MarketDataProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def get_profile(self, ticker: str) -> CompanyProfile | None:
        """Static company information. None if the ticker is unknown."""

    @abstractmethod
    async def get_quote(self, ticker: str) -> Quote | None:
        """Latest price snapshot. None if the ticker is unknown."""

    @abstractmethod
    async def get_quotes(self, tickers: list[str]) -> list[Quote]:
        """Lightweight snapshots for a watchlist. Unknown tickers are omitted, order kept."""

    @abstractmethod
    async def get_history(self, ticker: str, range_: str, interval: str) -> PriceHistory | None:
        """OHLCV bars. Parameters are pre-validated by app.services.market. None if no data."""

    @abstractmethod
    async def get_news(self, ticker: str, limit: int) -> NewsFeed:
        """Recent headlines. Empty feed (not None) when nothing is found."""


class FundamentalsProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def get_financials(self, ticker: str) -> Financials | None:
        """Annual and quarterly statements. None if the company is not an SEC filer."""

    @abstractmethod
    async def get_filings(
        self, ticker: str, forms: set[str] | None, limit: int
    ) -> FilingList | None:
        """Recent filings, newest first. None if the company is not an SEC filer."""


class MacroProvider(ABC):
    name: str = "abstract"

    @abstractmethod
    async def get_series(self, series_id: str, start: date | None = None) -> MacroSeries | None:
        """Observations for one series from `start` onwards. None if the id is unknown."""
