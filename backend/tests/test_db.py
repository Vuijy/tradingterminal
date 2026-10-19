import datetime as dt
from pathlib import Path

from sqlalchemy import inspect, select

from app.db.migrate import run_migrations
from app.db.models import AnalyzedFiling, Mention
from app.db.session import get_engine, get_session_factory


def test_migrations_create_schema(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'fresh.db').as_posix()}"
    run_migrations(url)
    tables = set(inspect(get_engine(url)).get_table_names())
    assert {"alembic_version", "analyzed_filings", "mentions", "relationship_runs"} <= tables
    run_migrations(url)  # idempotent


def test_orm_roundtrip(tmp_path: Path) -> None:
    url = f"sqlite:///{(tmp_path / 'orm.db').as_posix()}"
    run_migrations(url)
    factory = get_session_factory(url)
    with factory() as db:
        filing = AnalyzedFiling(
            accession="0000000001-25-000001",
            cik=1,
            form="10-K",
            filed=dt.date(2025, 2, 1),
            url="https://www.sec.gov/x",
            analyzed_at=dt.datetime(2026, 1, 1, tzinfo=dt.UTC),
            mention_count=1,
        )
        filing.mentions.append(
            Mention(
                source_cik=1,
                kind="customer_named",
                entity_text="Apple Inc.",
                entity_cik=320193,
                entity_ticker="AAPL",
                entity_name="Apple Inc.",
                confidence=0.9,
                percent=56.0,
                sentence="Apple accounted for 56% of net revenue.",
                pattern="customer_pct",
            )
        )
        db.add(filing)
        db.commit()
    with factory() as db:
        stored = db.scalars(select(Mention).where(Mention.entity_cik == 320193)).one()
        assert stored.filing.accession == "0000000001-25-000001"
        assert stored.percent == 56.0
