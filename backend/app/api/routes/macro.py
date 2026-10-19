import datetime as dt
from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query

from app.api.deps import MacroDep
from app.models.macro import MacroSeries, MacroSummary
from app.services.cache import cache
from app.services.macro import build_dashboard

router = APIRouter(prefix="/macro", tags=["macro"])

DASHBOARD_TTL = 900

SeriesId = Annotated[
    str,
    Path(min_length=1, max_length=40, pattern=r"^[A-Za-z0-9_]+$", description="FRED series id"),
]


@router.get("/dashboard", response_model=list[MacroSummary])
async def get_dashboard(provider: MacroDep) -> list[MacroSummary]:
    return await cache.get_or_set(
        f"macro:dashboard:{provider.name}", DASHBOARD_TTL, lambda: build_dashboard(provider)
    )


@router.get("/series/{series_id}", response_model=MacroSeries)
async def get_series(
    series_id: SeriesId,
    provider: MacroDep,
    start: Annotated[
        dt.date | None, Query(description="First observation date (inclusive)")
    ] = None,
) -> MacroSeries:
    series = await provider.get_series(series_id, start)
    if series is None:
        raise HTTPException(status_code=404, detail=f"Unknown FRED series '{series_id.upper()}'")
    return series
