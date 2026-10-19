"""filer name and ticker on analyzed filings

Revision ID: 0003
Revises: 0002
Create Date: 2026-10-19
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "0003"
down_revision: str | None = "0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    with op.batch_alter_table("analyzed_filings") as batch:
        batch.add_column(sa.Column("filer_name", sa.String(length=256), nullable=True))
        batch.add_column(sa.Column("filer_ticker", sa.String(length=16), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table("analyzed_filings") as batch:
        batch.drop_column("filer_ticker")
        batch.drop_column("filer_name")
