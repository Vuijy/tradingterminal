"""Yahoo Finance via the `yfinance` library.

The project's free source for market data (profile, quote, OHLCV history) and news.
No API key. It is scraped data with no SLA, so every call goes through the TTL cache
and nothing here should be called in a loop.
"""

import asyncio
import re
from datetime import UTC, datetime
from typing import Any

import pandas as pd
import yfinance as yf

from app.models.company import Candle, CompanyProfile, NewsFeed, NewsItem, PriceHistory, Quote
from app.services.cache import cache
from app.services.market import INTRADAY_INTERVALS
from app.services.providers.base import MarketDataProvider

INFO_TTL = 300
FAST_TTL = 30
HISTORY_TTL_INTRADAY = 60
HISTORY_TTL_DAILY = 300
NEWS_TTL = 300

# Legal-form words that only add noise to a news search ("Apple Inc." -> "Apple").
_NAME_NOISE = {
    "inc",
    "incorporated",
    "corp",
    "corporation",
    "co",
    "company",
    "ltd",
    "limited",
    "plc",
    "holding",
    "holdings",
    "group",
    "the",
    "new",
    "sa",
    "nv",
    "ag",
    "se",
}


def company_search_name(name: str) -> str:
    """Trim a legal company name down to what people actually search for."""
    words = re.split(r"[\s,]+", name.replace("(The)", " ").strip())
    kept = [w for w in words if w and w.strip(".").lower() not in _NAME_NOISE]
    cleaned = re.sub(r"\s*&\s*$", "", " ".join(kept)).strip()
    return cleaned or name.strip()


class YFinanceProvider(MarketDataProvider):
    name = "yfinance"

    # --- profile / quote -------------------------------------------------------------

    async def get_profile(self, ticker: str) -> CompanyProfile | None:
        info = await self._info(ticker)
        if not self._looks_valid(info):
            return None
        return CompanyProfile(
            ticker=ticker.upper(),
            name=info.get("longName") or info.get("shortName") or ticker.upper(),
            exchange=info.get("exchange"),
            currency=info.get("currency"),
            sector=info.get("sector"),
            industry=info.get("industry"),
            country=info.get("country"),
            website=info.get("website"),
            market_cap=info.get("marketCap"),
            employees=info.get("fullTimeEmployees"),
            description=info.get("longBusinessSummary"),
            source=self.name,
        )

    async def get_quote(self, ticker: str) -> Quote | None:
        info = await self._info(ticker)
        if not self._looks_valid(info):
            return None
        price = info.get("regularMarketPrice") or info.get("currentPrice")
        prev = info.get("regularMarketPreviousClose") or info.get("previousClose")
        change = change_pct = None
        if price is not None and prev:
            change = price - prev
            change_pct = change / prev * 100
        ts = info.get("regularMarketTime")
        as_of = datetime.fromtimestamp(ts, tz=UTC) if isinstance(ts, int | float) else None
        return Quote(
            ticker=ticker.upper(),
            price=price,
            previous_close=prev,
            change=change,
            change_pct=change_pct,
            currency=info.get("currency"),
            as_of=as_of,
            day_high=info.get("regularMarketDayHigh") or info.get("dayHigh"),
            day_low=info.get("regularMarketDayLow") or info.get("dayLow"),
            year_high=info.get("fiftyTwoWeekHigh"),
            year_low=info.get("fiftyTwoWeekLow"),
            volume=info.get("regularMarketVolume") or info.get("volume"),
            market_cap=info.get("marketCap"),
            source=self.name,
        )

    async def get_quotes(self, tickers: list[str]) -> list[Quote]:
        results = await asyncio.gather(*(self._fast_quote(t) for t in tickers))
        return [q for q in results if q is not None]

    async def _fast_quote(self, ticker: str) -> Quote | None:
        key = f"yf:fast:{ticker.upper()}"
        return await cache.get_or_set(
            key, FAST_TTL, lambda: asyncio.to_thread(self._fetch_fast_quote, ticker)
        )

    def _fetch_fast_quote(self, ticker: str) -> Quote | None:
        """`fast_info` is one small request per symbol, unlike the heavy `info` payload."""
        try:
            fi = yf.Ticker(ticker).fast_info
            price = _num(getattr(fi, "last_price", None))
        except Exception:
            return None
        if price is None:
            return None
        prev = _num(getattr(fi, "previous_close", None))
        change = price - prev if prev is not None else None
        change_pct = change / prev * 100 if change is not None and prev else None
        return Quote(
            ticker=ticker.upper(),
            price=price,
            previous_close=prev,
            change=change,
            change_pct=change_pct,
            currency=getattr(fi, "currency", None),
            day_high=_num(getattr(fi, "day_high", None)),
            day_low=_num(getattr(fi, "day_low", None)),
            year_high=_num(getattr(fi, "year_high", None)),
            year_low=_num(getattr(fi, "year_low", None)),
            volume=_num(getattr(fi, "last_volume", None)),
            market_cap=_num(getattr(fi, "market_cap", None)),
            source=self.name,
        )

    async def _info(self, ticker: str) -> dict[str, Any]:
        key = f"yf:info:{ticker.upper()}"
        return await cache.get_or_set(
            key, INFO_TTL, lambda: asyncio.to_thread(self._fetch_info, ticker)
        )

    @staticmethod
    def _fetch_info(ticker: str) -> dict[str, Any]:
        try:
            return yf.Ticker(ticker).info or {}
        except Exception:  # yfinance raises assorted errors for unknown symbols
            return {}

    @staticmethod
    def _looks_valid(info: dict[str, Any]) -> bool:
        return bool(info) and any(
            k in info for k in ("longName", "shortName", "regularMarketPrice")
        )

    # --- history ---------------------------------------------------------------------

    async def get_history(self, ticker: str, range_: str, interval: str) -> PriceHistory | None:
        key = f"yf:history:{ticker.upper()}:{range_}:{interval}"
        ttl = HISTORY_TTL_INTRADAY if interval in INTRADAY_INTERVALS else HISTORY_TTL_DAILY
        return await cache.get_or_set(
            key, ttl, lambda: asyncio.to_thread(self._fetch_history, ticker, range_, interval)
        )

    def _fetch_history(self, ticker: str, range_: str, interval: str) -> PriceHistory | None:
        try:
            t = yf.Ticker(ticker)
            df = t.history(period=range_, interval=interval, auto_adjust=False, actions=False)
        except Exception:
            return None
        if df is None or df.empty:
            return None
        meta = getattr(t, "history_metadata", None) or {}
        intraday = interval in INTRADAY_INTERVALS

        candles: dict[int, Candle] = {}
        for ts, o, h, lo, c, v in zip(
            df.index, df["Open"], df["High"], df["Low"], df["Close"], df["Volume"], strict=False
        ):
            if pd.isna(c) or pd.isna(o):
                continue
            if intraday:
                time_ = int(ts.timestamp())
            else:  # daily and coarser bars are dated, not timed: pin them to UTC midnight
                time_ = int(datetime(ts.year, ts.month, ts.day, tzinfo=UTC).timestamp())
            candles[time_] = Candle(  # later duplicates (partial bars) overwrite earlier ones
                time=time_,
                open=float(o),
                high=float(h),
                low=float(lo),
                close=float(c),
                volume=None if pd.isna(v) else float(v),
            )
        if not candles:
            return None
        return PriceHistory(
            ticker=ticker.upper(),
            range=range_,
            interval=interval,
            currency=meta.get("currency"),
            timezone=meta.get("exchangeTimezoneName"),
            candles=[candles[k] for k in sorted(candles)],
            source=self.name,
        )

    # --- news ------------------------------------------------------------------------

    async def get_news(self, ticker: str, limit: int) -> NewsFeed:
        key = f"yf:news:{ticker.upper()}:{limit}"

        async def load() -> NewsFeed:
            info = await self._info(ticker)  # cached; shared with profile/quote
            name = company_search_name(info.get("shortName") or info.get("longName") or "")
            return await asyncio.to_thread(self._fetch_news, ticker, name, limit)

        return await cache.get_or_set(key, NEWS_TTL, load)

    def _fetch_news(self, ticker: str, name: str, limit: int) -> NewsFeed:
        # Yahoo's symbol feed (query = ticker) tags everything with the symbol but is mostly
        # market-wide chatter; "<company> stock" returns headlines about the company itself.
        # Use the specific query first and top up from the symbol feed.
        queries = [f"{name} stock"] if name else []
        queries.append(ticker)

        items: dict[str, NewsItem] = {}
        for query in queries:
            parsed = [self._parse_news_item(e) for e in self._search_news(query, limit)]
            batch = sorted(
                (i for i in parsed if i is not None),
                key=lambda i: i.published_at or datetime.min.replace(tzinfo=UTC),
                reverse=True,
            )
            for item in batch:
                items.setdefault(item.url, item)
            if len(items) >= limit:
                break
        return NewsFeed(ticker=ticker.upper(), items=list(items.values())[:limit], source=self.name)

    @staticmethod
    def _search_news(query: str, limit: int) -> list[dict[str, Any]]:
        try:
            return yf.Search(query, news_count=limit, max_results=1).news or []
        except Exception:
            return []

    @staticmethod
    def _parse_news_item(entry: dict[str, Any]) -> NewsItem | None:
        content = entry.get("content")
        if isinstance(content, dict):  # shape returned by Ticker.get_news
            title = content.get("title")
            url = (content.get("canonicalUrl") or {}).get("url") or (
                content.get("clickThroughUrl") or {}
            ).get("url")
            publisher = (content.get("provider") or {}).get("displayName")
            published = _parse_iso(content.get("pubDate") or content.get("displayTime"))
            thumb = _smallest_thumbnail(content.get("thumbnail"))
            item_id = entry.get("id") or content.get("id") or url
            related: list[str] = []
        else:  # shape returned by Search(...).news
            title = entry.get("title")
            url = entry.get("link")
            publisher = entry.get("publisher")
            ts = entry.get("providerPublishTime")
            published = datetime.fromtimestamp(ts, tz=UTC) if isinstance(ts, int | float) else None
            thumb = _smallest_thumbnail(entry.get("thumbnail"))
            item_id = entry.get("uuid") or url
            related = [str(t) for t in entry.get("relatedTickers") or []]
        if not title or not url:
            return None
        return NewsItem(
            id=str(item_id),
            title=str(title),
            publisher=publisher,
            url=str(url),
            published_at=published,
            thumbnail_url=thumb,
            related_tickers=related,
        )


def _num(value: Any) -> float | None:
    """fast_info returns numpy scalars, NaN for missing values, or raises; normalise to float."""
    if value is None:
        return None
    try:
        f = float(value)
    except (TypeError, ValueError):
        return None
    return None if f != f else f  # NaN check


def _parse_iso(value: Any) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(str(value).replace("Z", "+00:00"))
    except ValueError:
        return None


def _smallest_thumbnail(thumbnail: Any) -> str | None:
    if not isinstance(thumbnail, dict):
        return None
    resolutions = thumbnail.get("resolutions") or []
    if not resolutions:
        return None
    smallest = min(resolutions, key=lambda r: r.get("width") or 10**9)
    url = smallest.get("url")
    return str(url) if url else None
