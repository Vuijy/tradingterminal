"""Macro dashboard: latest value, change and year-over-year for each curated series."""

import asyncio
from datetime import date, timedelta

from app.models.macro import MacroObservation, MacroSeries, MacroSummary
from app.services.macro_registry import MACRO_SERIES, SeriesMeta
from app.services.providers.base import MacroProvider

# Enough history for a year-over-year comparison even for quarterly series that publish
# with a lag (GDP's latest point can be six months old).
LOOKBACK_DAYS = 800
YOY_TOLERANCE_DAYS = 20


def _yoy_pct(observations: list[MacroObservation]) -> float | None:
    if len(observations) < 2:
        return None
    last = observations[-1]
    target = last.date - timedelta(days=365)
    closest = min(observations, key=lambda o: abs((o.date - target).days))
    if abs((closest.date - target).days) > YOY_TOLERANCE_DAYS or closest.value == 0:
        return None
    return (last.value / closest.value - 1) * 100


def summarize(meta: SeriesMeta, series: MacroSeries | None) -> MacroSummary:
    base = MacroSummary(
        series_id=meta.series_id,
        title=meta.title,
        unit=meta.unit,
        frequency=meta.frequency,
        group=meta.group,
    )
    if series is None or not series.observations:
        return base
    obs = series.observations
    last = obs[-1]
    prev = obs[-2] if len(obs) > 1 else None
    change = last.value - prev.value if prev else None
    change_pct = (change / prev.value * 100) if prev and change is not None and prev.value else None
    return base.model_copy(
        update={
            "latest_value": last.value,
            "latest_date": last.date,
            "previous_value": prev.value if prev else None,
            "previous_date": prev.date if prev else None,
            "change": change,
            "change_pct": change_pct,
            "yoy_pct": _yoy_pct(obs),
        }
    )


async def build_dashboard(provider: MacroProvider) -> list[MacroSummary]:
    start = date.today() - timedelta(days=LOOKBACK_DAYS)
    results = await asyncio.gather(
        *(provider.get_series(m.series_id, start) for m in MACRO_SERIES),
        return_exceptions=True,
    )
    out: list[MacroSummary] = []
    for meta, result in zip(MACRO_SERIES, results, strict=True):
        series = None if isinstance(result, BaseException) else result
        out.append(summarize(meta, series))
    return out
