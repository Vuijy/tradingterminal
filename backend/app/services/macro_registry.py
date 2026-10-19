"""Curated FRED series shown on the macro dashboard.

Any FRED series id works with the series endpoint; this list only decides what the
dashboard shows by default and supplies display metadata when no API key is set
(the keyless CSV endpoint carries no titles or units).
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class SeriesMeta:
    series_id: str
    title: str
    unit: str
    frequency: str
    group: str


MACRO_SERIES: tuple[SeriesMeta, ...] = (
    SeriesMeta("DGS10", "US 10Y Treasury", "%", "daily", "rates"),
    SeriesMeta("DGS2", "US 2Y Treasury", "%", "daily", "rates"),
    SeriesMeta("T10Y2Y", "10Y-2Y spread", "%", "daily", "rates"),
    SeriesMeta("FEDFUNDS", "Fed funds effective", "%", "monthly", "rates"),
    SeriesMeta("MORTGAGE30US", "30Y mortgage rate", "%", "weekly", "rates"),
    SeriesMeta("CPIAUCSL", "CPI (all items)", "index", "monthly", "inflation"),
    SeriesMeta("T10YIE", "10Y breakeven inflation", "%", "daily", "inflation"),
    SeriesMeta("UNRATE", "Unemployment rate", "%", "monthly", "labor"),
    SeriesMeta("PAYEMS", "Nonfarm payrolls", "thousands", "monthly", "labor"),
    SeriesMeta("GDPC1", "Real GDP", "bn 2017 USD", "quarterly", "growth"),
    SeriesMeta("VIXCLS", "VIX", "index", "daily", "markets"),
    SeriesMeta("DTWEXBGS", "USD index (broad)", "index", "daily", "markets"),
    SeriesMeta("DCOILWTICO", "WTI crude", "USD/bbl", "daily", "commodities"),
)

SERIES_BY_ID: dict[str, SeriesMeta] = {m.series_id: m for m in MACRO_SERIES}
