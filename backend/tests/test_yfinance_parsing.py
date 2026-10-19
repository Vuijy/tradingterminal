"""Pure-function tests for the yfinance provider (no network)."""

import pytest

from app.services.providers.yfinance_provider import YFinanceProvider, company_search_name


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Apple Inc.", "Apple"),
        ("NVIDIA Corporation", "NVIDIA"),
        ("Ford Motor Company", "Ford Motor"),
        ("Meta Platforms, Inc.", "Meta Platforms"),
        ("The Coca-Cola Company", "Coca-Cola"),
        ("JPMorgan Chase & Co.", "JPMorgan Chase"),
        (
            "Taiwan Semiconductor Manufacturing Company Limited",
            "Taiwan Semiconductor Manufacturing",
        ),
        ("SAP SE", "SAP"),
        ("Berkshire Hathaway Inc. New", "Berkshire Hathaway"),
        ("Inc.", "Inc."),  # never return an empty query
    ],
)
def test_company_search_name(raw: str, expected: str) -> None:
    assert company_search_name(raw) == expected


def test_parse_search_shape() -> None:
    entry = {
        "uuid": "abc",
        "title": "Apple ships thing",
        "publisher": "Wire",
        "link": "https://example.com/a",
        "providerPublishTime": 1_700_000_000,
        "thumbnail": {
            "resolutions": [
                {"url": "https://img/large.jpg", "width": 1200},
                {"url": "https://img/small.jpg", "width": 140},
            ]
        },
        "relatedTickers": ["AAPL", "MSFT"],
    }
    item = YFinanceProvider._parse_news_item(entry)
    assert item is not None
    assert item.id == "abc"
    assert item.publisher == "Wire"
    assert item.published_at is not None and item.published_at.year == 2023
    assert item.thumbnail_url == "https://img/small.jpg"
    assert item.related_tickers == ["AAPL", "MSFT"]


def test_parse_ticker_news_shape() -> None:
    entry = {
        "id": "xyz",
        "content": {
            "title": "Headline",
            "pubDate": "2026-01-02T03:04:05Z",
            "provider": {"displayName": "Reuters"},
            "canonicalUrl": {"url": "https://example.com/b"},
            "thumbnail": None,
        },
    }
    item = YFinanceProvider._parse_news_item(entry)
    assert item is not None
    assert item.id == "xyz"
    assert item.publisher == "Reuters"
    assert item.url == "https://example.com/b"
    assert item.published_at is not None and item.published_at.isoformat().startswith("2026-01-02")
    assert item.thumbnail_url is None


def test_parse_rejects_items_without_title_or_url() -> None:
    assert YFinanceProvider._parse_news_item({"title": "x"}) is None
    assert YFinanceProvider._parse_news_item({"link": "https://e.com"}) is None
