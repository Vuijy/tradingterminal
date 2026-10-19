"""ORM models. Every change here needs a matching Alembic migration in backend/alembic/versions.

Tables back the supply-chain feature: each parsed filing is recorded once, every
relationship sentence extracted from it becomes a `Mention`, and assembled graphs are
cached per company so the expensive full-text reverse search runs rarely.
"""

import datetime as dt

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


class AnalyzedFiling(Base):
    __tablename__ = "analyzed_filings"

    accession: Mapped[str] = mapped_column(String(25), primary_key=True)
    cik: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    form: Mapped[str] = mapped_column(String(16), nullable=False)
    filed: Mapped[dt.date | None] = mapped_column(Date, nullable=True)
    url: Mapped[str] = mapped_column(Text, nullable=False)
    analyzed_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    mention_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    filer_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    filer_ticker: Mapped[str | None] = mapped_column(String(16), nullable=True)

    mentions: Mapped[list["Mention"]] = relationship(
        back_populates="filing", cascade="all, delete-orphan"
    )


class Mention(Base):
    """One sentence in one filing that names a counterparty (or an anonymous customer)."""

    __tablename__ = "mentions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    source_cik: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    source_accession: Mapped[str] = mapped_column(
        String(25),
        ForeignKey("analyzed_filings.accession", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    section: Mapped[str | None] = mapped_column(String(32), nullable=True)
    # customer_named | customer_anonymous | supplier | competitor | partner
    kind: Mapped[str] = mapped_column(String(24), nullable=False)
    entity_text: Mapped[str] = mapped_column(String(256), nullable=False)
    entity_cik: Mapped[int | None] = mapped_column(Integer, nullable=True, index=True)
    entity_ticker: Mapped[str | None] = mapped_column(String(16), nullable=True)
    entity_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    percent: Mapped[float | None] = mapped_column(Float, nullable=True)
    sentence: Mapped[str] = mapped_column(Text, nullable=False)
    pattern: Mapped[str | None] = mapped_column(String(48), nullable=True)

    filing: Mapped[AnalyzedFiling] = relationship(back_populates="mentions")


class CacheEntry(Base):
    """Second level of app.services.cache: slow upstream payloads survive restarts here."""

    __tablename__ = "cache_entries"

    key: Mapped[str] = mapped_column(String(255), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)  # JSON, see persistent_cache.py
    expires_at: Mapped[float] = mapped_column(Float, nullable=False, index=True)  # epoch seconds
    updated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)


class RelationshipRun(Base):
    """Cached assembled graph for one company (JSON of RelationshipGraph, see app/models)."""

    __tablename__ = "relationship_runs"

    cik: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticker: Mapped[str] = mapped_column(String(16), nullable=False)
    status: Mapped[str] = mapped_column(String(24), nullable=False)
    generated_at: Mapped[dt.datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    graph_json: Mapped[str] = mapped_column(Text, nullable=False)
