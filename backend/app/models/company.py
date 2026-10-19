"""Pydantic schemas returned by the API. Provider-agnostic on purpose."""

from datetime import datetime

from pydantic import BaseModel, Field


class CompanyProfile(BaseModel):
    ticker: str = Field(..., examples=["AAPL"])
    name: str
    exchange: str | None = None
    currency: str | None = None
    sector: str | None = None
    industry: str | None = None
    country: str | None = None
    website: str | None = None
    market_cap: float | None = None
    employees: int | None = None
    description: str | None = None
    source: str = Field(..., description="Data provider that produced this record")


class Quote(BaseModel):
    ticker: str
    price: float | None = None
    previous_close: float | None = None
    change: float | None = None
    change_pct: float | None = None
    currency: str | None = None
    as_of: datetime | None = None
    day_high: float | None = None
    day_low: float | None = None
    year_high: float | None = None
    year_low: float | None = None
    volume: float | None = None
    market_cap: float | None = None
    source: str


class Candle(BaseModel):
    time: int = Field(..., description="Bar open time as Unix seconds (UTC)")
    open: float
    high: float
    low: float
    close: float
    volume: float | None = None


class PriceHistory(BaseModel):
    ticker: str
    range: str
    interval: str
    currency: str | None = None
    timezone: str | None = Field(None, description="Exchange time zone (IANA name)")
    candles: list[Candle]
    source: str


class NewsItem(BaseModel):
    id: str
    title: str
    publisher: str | None = None
    url: str
    published_at: datetime | None = None
    thumbnail_url: str | None = None
    related_tickers: list[str] = Field(default_factory=list)


class NewsFeed(BaseModel):
    ticker: str
    items: list[NewsItem]
    source: str
