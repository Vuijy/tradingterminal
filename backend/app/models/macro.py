"""Schemas for macro series (FRED)."""

import datetime as dt

from pydantic import BaseModel


class MacroObservation(BaseModel):
    date: dt.date
    value: float


class MacroSeries(BaseModel):
    series_id: str
    title: str
    unit: str | None = None
    frequency: str | None = None
    observations: list[MacroObservation]
    source: str


class MacroSummary(BaseModel):
    series_id: str
    title: str
    unit: str | None = None
    frequency: str | None = None
    group: str
    latest_value: float | None = None
    latest_date: dt.date | None = None
    previous_value: float | None = None
    previous_date: dt.date | None = None
    change: float | None = None
    change_pct: float | None = None
    yoy_pct: float | None = None
