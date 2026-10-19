from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.deps import RelationshipsDep
from app.models.relationships import RelationshipGraph

router = APIRouter(prefix="/companies", tags=["relationships"])

Ticker = Annotated[
    str,
    Path(
        min_length=1, max_length=12, pattern=r"^[A-Za-z0-9.\-^=]+$", description="Ticker, e.g. AAPL"
    ),
]


@router.get("/{ticker}/relationships", response_model=RelationshipGraph)
async def get_relationships(
    ticker: Ticker,
    service: RelationshipsDep,
    deep: Annotated[
        bool,
        Query(
            description="Also search other filers' 10-Ks that name the company (slow on first run)"
        ),
    ] = False,
    refresh: Annotated[bool, Query(description="Ignore the cached graph and rebuild")] = False,
) -> RelationshipGraph:
    """Suppliers, customers, competitors and partners mined from SEC filings.

    `deep=false` parses the company's own latest 10-K and returns within seconds.
    `deep=true` adds a full-text search across EDGAR for filers that name the company and
    analyses up to 30 of their documents; results are cached for a week.
    """
    graph = await service.get_graph(ticker, deep=deep, refresh=refresh)
    if graph is None:
        raise HTTPException(
            status_code=404,
            detail=(
                f"'{ticker.upper()}' is not an SEC registrant. Relationships are mined from "
                "10-K filings, so only US-listed companies are covered."
            ),
        )
    return graph
