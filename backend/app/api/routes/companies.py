from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.deps import FundamentalsDep, ProviderDep
from app.models.company import CompanyProfile, NewsFeed, PriceHistory, Quote
from app.models.fundamentals import FilingList, Financials
from app.services.market import validate_history_params

router = APIRouter(prefix="/companies", tags=["companies"])

Ticker = Annotated[
    str,
    Path(
        min_length=1,
        max_length=12,
        pattern=r"^[A-Za-z0-9.\-^=]+$",
        description="Exchange ticker symbol, e.g. AAPL",
    ),
]


@router.get("/{ticker}", response_model=CompanyProfile)
async def get_company(ticker: Ticker, provider: ProviderDep) -> CompanyProfile:
    profile = await provider.get_profile(ticker)
    if profile is None:
        raise HTTPException(
            status_code=404, detail=f"No company found for ticker '{ticker.upper()}'"
        )
    return profile


@router.get("/{ticker}/quote", response_model=Quote)
async def get_quote(ticker: Ticker, provider: ProviderDep) -> Quote:
    quote = await provider.get_quote(ticker)
    if quote is None:
        raise HTTPException(status_code=404, detail=f"No quote available for '{ticker.upper()}'")
    return quote


@router.get("/{ticker}/history", response_model=PriceHistory)
async def get_history(
    ticker: Ticker,
    provider: ProviderDep,
    range_: Annotated[
        str, Query(alias="range", description="1d 5d 1mo 3mo 6mo ytd 1y 2y 5y 10y max")
    ] = "6mo",
    interval: Annotated[str, Query(description="1m 2m 5m 15m 30m 1h 1d 1wk 1mo")] = "1d",
) -> PriceHistory:
    error = validate_history_params(range_, interval)
    if error:
        raise HTTPException(status_code=422, detail=error)
    history = await provider.get_history(ticker, range_, interval)
    if history is None:
        raise HTTPException(
            status_code=404,
            detail=f"No price history for '{ticker.upper()}' ({range_}/{interval})",
        )
    return history


@router.get("/{ticker}/news", response_model=NewsFeed)
async def get_news(
    ticker: Ticker,
    provider: ProviderDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 15,
) -> NewsFeed:
    return await provider.get_news(ticker, limit)


@router.get("/{ticker}/fundamentals", response_model=Financials)
async def get_fundamentals(ticker: Ticker, fundamentals: FundamentalsDep) -> Financials:
    result = await fundamentals.get_financials(ticker)
    if result is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"No SEC filings found for '{ticker.upper()}'. "
                "Only companies listed in the US file with EDGAR."
            ),
        )
    return result


@router.get("/{ticker}/filings", response_model=FilingList)
async def get_filings(
    ticker: Ticker,
    fundamentals: FundamentalsDep,
    forms: Annotated[str, Query(description="Comma-separated form types; empty for all")] = (
        "10-K,10-Q,8-K"
    ),
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> FilingList:
    wanted = {f.strip().upper() for f in forms.split(",") if f.strip()} or None
    result = await fundamentals.get_filings(ticker, wanted, limit)
    if result is None:
        raise HTTPException(status_code=404, detail=f"No SEC filings found for '{ticker.upper()}'.")
    return result
