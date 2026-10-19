import re
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.api.deps import ProviderDep
from app.models.company import Quote

router = APIRouter(prefix="/quotes", tags=["quotes"])

MAX_TICKERS = 30
_TICKER_RE = re.compile(r"^[A-Za-z0-9.\-^=]{1,12}$")


@router.get("", response_model=list[Quote])
async def get_quotes(
    provider: ProviderDep,
    tickers: Annotated[str, Query(min_length=1, description="Comma-separated symbols, max 30")],
) -> list[Quote]:
    """Lightweight quotes for a watchlist. Unknown symbols are omitted from the result."""
    seen: set[str] = set()
    symbols: list[str] = []
    for raw in tickers.split(","):
        symbol = raw.strip().upper()
        if not symbol or symbol in seen:
            continue
        if not _TICKER_RE.match(symbol):
            raise HTTPException(status_code=422, detail=f"Invalid ticker '{symbol}'")
        seen.add(symbol)
        symbols.append(symbol)
    if not symbols:
        raise HTTPException(status_code=422, detail="Provide at least one ticker")
    if len(symbols) > MAX_TICKERS:
        raise HTTPException(status_code=422, detail=f"At most {MAX_TICKERS} tickers per request")
    return await provider.get_quotes(symbols)
