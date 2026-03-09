"""create user_profiles table if missing

Revision ID: 20260302_03
Revises: 20260302_02
Create Date: 2026-03-02 00:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_03"
down_revision: Union[str, Sequence[str], None] = "20260302_02"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "user_profiles" in tables:
        return

    op.create_table(
        "user_profiles",
        sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
        sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("org_type", sa.String(), nullable=True),
        sa.Column("country", sa.String(length=2), nullable=True),
        sa.Column("trl_min", sa.Integer(), nullable=True),
        sa.Column("trl_max", sa.Integer(), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("problem_frames", sa.JSON(), nullable=True),
        sa.Column("funding_types", sa.JSON(), nullable=True),
        sa.Column("collaboration", sa.String(), nullable=True),
        sa.Column("budget_min", sa.Integer(), nullable=True),
        sa.Column("budget_max", sa.Integer(), nullable=True),
        sa.Column("deadline_horizon", sa.String(), nullable=True),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "user_profiles" in tables:
        op.drop_table("user_profiles")
