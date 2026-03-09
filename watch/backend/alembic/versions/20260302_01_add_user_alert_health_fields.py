"""add user-level alert health fields

Revision ID: 20260302_01
Revises: 20260301_01
Create Date: 2026-03-02 00:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_01"
down_revision: Union[str, Sequence[str], None] = "20260301_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    if "alert_last_error" not in columns:
        op.add_column("users", sa.Column("alert_last_error", sa.String(), nullable=True))
    if "alert_last_error_at" not in columns:
        op.add_column("users", sa.Column("alert_last_error_at", sa.DateTime(timezone=True), nullable=True))
    if "alert_last_ok_at" not in columns:
        op.add_column("users", sa.Column("alert_last_ok_at", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("users")}

    if "alert_last_ok_at" in columns:
        op.drop_column("users", "alert_last_ok_at")
    if "alert_last_error_at" in columns:
        op.drop_column("users", "alert_last_error_at")
    if "alert_last_error" in columns:
        op.drop_column("users", "alert_last_error")
