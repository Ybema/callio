"""add crawl_config to sources

Revision ID: 20260302_08
Revises: 20260302_07
Create Date: 2026-03-02 21:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_08"
down_revision: Union[str, Sequence[str], None] = "20260302_07"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _column_names(bind, table_name: str) -> set[str]:
    inspector = sa.inspect(bind)
    try:
        cols = inspector.get_columns(table_name)
    except Exception:
        return set()
    return {c.get("name") for c in cols}


def upgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "sources")
    if not columns:
        return
    if "crawl_config" not in columns:
        op.add_column("sources", sa.Column("crawl_config", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "sources")
    if not columns:
        return
    if "crawl_config" in columns:
        op.drop_column("sources", "crawl_config")
