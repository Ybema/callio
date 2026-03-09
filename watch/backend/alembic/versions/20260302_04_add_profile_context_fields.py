"""add context url/text fields to user_profiles

Revision ID: 20260302_04
Revises: 20260302_03
Create Date: 2026-03-02 13:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_04"
down_revision: Union[str, Sequence[str], None] = "20260302_03"
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
    columns = _column_names(bind, "user_profiles")
    if not columns:
        return

    if "context_url" not in columns:
        op.add_column("user_profiles", sa.Column("context_url", sa.Text(), nullable=True))
    if "context_text" not in columns:
        op.add_column("user_profiles", sa.Column("context_text", sa.Text(), nullable=True))
    if "context_last_fetched_at" not in columns:
        op.add_column("user_profiles", sa.Column("context_last_fetched_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "user_profiles")
    if not columns:
        return

    if "context_last_fetched_at" in columns:
        op.drop_column("user_profiles", "context_last_fetched_at")
    if "context_text" in columns:
        op.drop_column("user_profiles", "context_text")
    if "context_url" in columns:
        op.drop_column("user_profiles", "context_url")
