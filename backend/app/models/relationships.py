"""Schemas for the supply-chain / relationships view (suppliers, customers, competitors).

Directional semantics, always expressed from the point of view of the centre company X:
  - supplier:   the related company sells to X   (X buys from it)
  - customer:   the related company buys from X  (X sells to it)
  - competitor: symmetric
  - partner:    named strategic/technology partner, direction not implied

Evidence always names the filer whose document makes the statement. A supplier's 10-K
saying "Apple accounted for 56% of our revenue" is evidence that the filer is a
*supplier* of Apple and that Apple is a *customer* of the filer.
"""

import datetime as dt
from typing import Literal

from pydantic import BaseModel, Field

Relation = Literal["supplier", "customer", "competitor", "partner"]


class RelationshipEvidence(BaseModel):
    source_cik: int = Field(
        ..., description="CIK of the filer whose document contains the sentence"
    )
    source_name: str
    source_ticker: str | None = None
    form: str
    filed: dt.date | None = None
    accession: str
    url: str = Field(..., description="Primary document URL on sec.gov")
    section: str | None = Field(None, description="Item 1, Item 1A, Item 7, Notes, ...")
    snippet: str = Field(
        ..., description="The sentence (or short passage) supporting the relationship"
    )
    percent: float | None = Field(
        None,
        description="Share of the speaking filer's revenue from the counterparty, if stated",
    )
    method: Literal["own_filing", "full_text_search", "stored"] = "own_filing"
    pattern: str | None = Field(None, description="Id of the extraction rule that matched")


class RelatedCompany(BaseModel):
    name: str = Field(..., description="Resolved SEC title when known, else the name as written")
    ticker: str | None = None
    cik: int | None = None
    relation: Relation
    confidence: float = Field(..., ge=0, le=1)
    revenue_share_pct: float | None = Field(
        None,
        description=(
            "For customers: share of X's revenue they represent. For suppliers: share of the "
            "supplier's revenue that X represents (how dependent the supplier is on X)."
        ),
    )
    evidence: list[RelationshipEvidence] = Field(default_factory=list)


class AnonymousCustomer(BaseModel):
    label: str = Field(..., description="e.g. 'Customer A', 'one customer', 'two customers'")
    percent: float | None = None
    evidence: RelationshipEvidence


class RelationshipGraph(BaseModel):
    ticker: str
    cik: int
    name: str
    suppliers: list[RelatedCompany] = Field(default_factory=list)
    customers: list[RelatedCompany] = Field(default_factory=list)
    competitors: list[RelatedCompany] = Field(default_factory=list)
    partners: list[RelatedCompany] = Field(default_factory=list)
    anonymous_customers: list[AnonymousCustomer] = Field(default_factory=list)
    analyzed_filings: list[str] = Field(
        default_factory=list, description="Accessions whose text was analysed for this graph"
    )
    status: Literal["own_filing_only", "complete"] = Field(
        ...,
        description="own_filing_only: only X's 10-K parsed. complete: reverse search done too",
    )
    generated_at: dt.datetime
    source: str = "sec-edgar"
