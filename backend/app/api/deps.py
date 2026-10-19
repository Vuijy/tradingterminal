"""FastAPI dependencies shared across routes.

Tests override these via `app.dependency_overrides[...]` so no network calls happen
in the test suite.
"""

from functools import lru_cache
from typing import Annotated

from fastapi import Depends

from app.config import get_settings
from app.services.filing_text import FilingTextStore
from app.services.providers.base import FundamentalsProvider, MacroProvider, MarketDataProvider
from app.services.providers.edgar_provider import EdgarProvider
from app.services.providers.efts import EdgarFullTextSearch
from app.services.providers.fred_provider import FredProvider
from app.services.providers.yfinance_provider import YFinanceProvider
from app.services.relationships import RelationshipService


@lru_cache
def get_provider() -> MarketDataProvider:
    return YFinanceProvider()


@lru_cache
def get_edgar_provider() -> EdgarProvider:
    return EdgarProvider(user_agent=get_settings().sec_edgar_user_agent)


@lru_cache
def get_fundamentals_provider() -> FundamentalsProvider:
    return get_edgar_provider()


@lru_cache
def get_macro_provider() -> MacroProvider:
    return FredProvider(api_key=get_settings().fred_api_key)


@lru_cache
def get_relationship_service() -> RelationshipService:
    settings = get_settings()
    return RelationshipService(
        edgar=get_edgar_provider(),
        efts=EdgarFullTextSearch(user_agent=settings.sec_edgar_user_agent),
        texts=FilingTextStore(settings.sec_edgar_user_agent, settings.data_dir / "filings"),
    )


ProviderDep = Annotated[MarketDataProvider, Depends(get_provider)]
FundamentalsDep = Annotated[FundamentalsProvider, Depends(get_fundamentals_provider)]
MacroDep = Annotated[MacroProvider, Depends(get_macro_provider)]
RelationshipsDep = Annotated[RelationshipService, Depends(get_relationship_service)]
