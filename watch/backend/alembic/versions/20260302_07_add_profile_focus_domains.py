"""add focus_domains to user_profiles

Revision ID: 20260302_07
Revises: 20260302_06
Create Date: 2026-03-02 17:20:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_07"
down_revision: Union[str, Sequence[str], None] = "20260302_06"
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
    if "focus_domains" not in columns:
        op.add_column("user_profiles", sa.Column("focus_domains", sa.JSON(), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    columns = _column_names(bind, "user_profiles")
    if not columns:
        return
    if "focus_domains" in columns:
        op.drop_column("user_profiles", "focus_domains")
