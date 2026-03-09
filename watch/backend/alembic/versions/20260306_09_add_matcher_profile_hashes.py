"""add matcher profile hash columns

Revision ID: 20260306_09
Revises: 20260302_08
Create Date: 2026-03-06 18:35:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260306_09"
down_revision: Union[str, Sequence[str], None] = "20260302_08"
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

    profile_columns = _column_names(bind, "user_profiles")
    if profile_columns and "matcher_profile_hash" not in profile_columns:
        op.add_column(
            "user_profiles",
            sa.Column("matcher_profile_hash", sa.String(length=64), nullable=True),
        )

    seen_call_columns = _column_names(bind, "seen_calls")
    if seen_call_columns and "scored_profile_hash" not in seen_call_columns:
        op.add_column(
            "seen_calls",
            sa.Column("scored_profile_hash", sa.String(length=64), nullable=True),
        )


def downgrade() -> None:
    bind = op.get_bind()

    seen_call_columns = _column_names(bind, "seen_calls")
    if seen_call_columns and "scored_profile_hash" in seen_call_columns:
        op.drop_column("seen_calls", "scored_profile_hash")

    profile_columns = _column_names(bind, "user_profiles")
    if profile_columns and "matcher_profile_hash" in profile_columns:
        op.drop_column("user_profiles", "matcher_profile_hash")

