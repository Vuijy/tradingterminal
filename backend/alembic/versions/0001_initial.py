"""initial tables for the supply-chain feature

Revision ID: 0001
Revises:
Create Date: 2026-10-18
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0001"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "analyzed_filings",
        sa.Column("accession", sa.String(length=25), primary_key=True),
        sa.Column("cik", sa.Integer(), nullable=False),
        sa.Column("form", sa.String(length=16), nullable=False),
        sa.Column("filed", sa.Date(), nullable=True),
        sa.Column("url", sa.Text(), nullable=False),
        sa.Column("analyzed_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("mention_count", sa.Integer(), nullable=False, server_default="0"),
    )
    op.create_index("ix_analyzed_filings_cik", "analyzed_filings", ["cik"])

    op.create_table(
        "mentions",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("source_cik", sa.Integer(), nullable=False),
        sa.Column(
            "source_accession",
            sa.String(length=25),
            sa.ForeignKey("analyzed_filings.accession", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("section", sa.String(length=32), nullable=True),
        sa.Column("kind", sa.String(length=24), nullable=False),
        sa.Column("entity_text", sa.String(length=256), nullable=False),
        sa.Column("entity_cik", sa.Integer(), nullable=True),
        sa.Column("entity_ticker", sa.String(length=16), nullable=True),
        sa.Column("entity_name", sa.String(length=256), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("percent", sa.Float(), nullable=True),
        sa.Column("sentence", sa.Text(), nullable=False),
        sa.Column("pattern", sa.String(length=48), nullable=True),
    )
    op.create_index("ix_mentions_source_cik", "mentions", ["source_cik"])
    op.create_index("ix_mentions_source_accession", "mentions", ["source_accession"])
    op.create_index("ix_mentions_entity_cik", "mentions", ["entity_cik"])

    op.create_table(
        "relationship_runs",
        sa.Column("cik", sa.Integer(), primary_key=True),
        sa.Column("ticker", sa.String(length=16), nullable=False),
        sa.Column("status", sa.String(length=24), nullable=False),
        sa.Column("generated_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("graph_json", sa.Text(), nullable=False),
    )


def downgrade() -> None:
    op.drop_table("relationship_runs")
    op.drop_index("ix_mentions_entity_cik", table_name="mentions")
    op.drop_index("ix_mentions_source_accession", table_name="mentions")
    op.drop_index("ix_mentions_source_cik", table_name="mentions")
    op.drop_table("mentions")
    op.drop_index("ix_analyzed_filings_cik", table_name="analyzed_filings")
    op.drop_table("analyzed_filings")
