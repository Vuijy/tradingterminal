"""Schemas for SEC EDGAR fundamentals and filings."""

import datetime as dt

from pydantic import BaseModel, Field


class ConceptMeta(BaseModel):
    key: str
    label: str
    kind: str = Field(..., description="'duration' (income/cash-flow) or 'instant' (balance sheet)")
    unit: str


class FinancialPeriod(BaseModel):
    period: str = Field(..., description="Display label, e.g. 'FY2025' or 'Q3 FY2026'")
    fiscal_year: int
    fiscal_period: str = Field(..., description="FY, Q1, Q2, Q3 or Q4")
    start: dt.date | None = None
    end: dt.date
    filed: dt.date | None = None
    form: str | None = None
    derived: bool = Field(False, description="True when Q4 was computed as FY minus Q1-Q3")
    values: dict[str, float | None]


class Financials(BaseModel):
    ticker: str
    cik: int
    entity_name: str
    currency: str = "USD"
    concepts: list[ConceptMeta]
    annual: list[FinancialPeriod] = Field(..., description="Newest first")
    quarterly: list[FinancialPeriod] = Field(..., description="Newest first")
    source: str


class Filing(BaseModel):
    accession: str
    form: str
    filed: dt.date
    report_date: dt.date | None = None
    description: str | None = None
    url: str


class FilingList(BaseModel):
    ticker: str
    cik: int
    entity_name: str | None = None
    filings: list[Filing]
    source: str
