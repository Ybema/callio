"""add relevance cache fields to seen_calls

Revision ID: 20260302_06
Revises: 20260302_05
Create Date: 2026-03-02 15:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_06"
down_revision: Union[str, Sequence[str], None] = "20260302_05"
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
    columns = _column_names(bind, "seen_calls")
    if not columns:
        return

    if "relevance_score" not in columns:
        op.add_column("seen_calls", sa.Column("relevance_score", sa.Integer(), nullable=True))
    if "relevance_reason" not in columns:
        op.add_column("seen_calls", sa.Column("relevance_reason", sa.Text(), nullable=True))
    if "scored_at" not in columns:
        op.add_column("seen_calls", sa.Column("scored_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "seen_calls")
    if not columns:
        return

    if "scored_at" in columns:
        op.drop_column("seen_calls", "scored_at")
    if "relevance_reason" in columns:
        op.drop_column("seen_calls", "relevance_reason")
    if "relevance_score" in columns:
        op.drop_column("seen_calls", "relevance_score")
