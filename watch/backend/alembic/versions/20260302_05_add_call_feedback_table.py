"""add call feedback table

Revision ID: 20260302_05
Revises: 20260302_04
Create Date: 2026-03-02 14:05:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_05"
down_revision: Union[str, Sequence[str], None] = "20260302_04"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "call_feedback" not in tables:
        op.create_table(
            "call_feedback",
            sa.Column("id", sa.String(length=36), primary_key=True, nullable=False),
            sa.Column("user_id", sa.String(length=36), sa.ForeignKey("users.id"), nullable=False),
            sa.Column("seen_call_id", sa.String(length=36), sa.ForeignKey("seen_calls.id"), nullable=False),
            sa.Column("label", sa.String(length=20), nullable=False),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=True),
        )

    indexes = {idx["name"] for idx in inspector.get_indexes("call_feedback")}
    if "ix_call_feedback_user_id" not in indexes:
        op.create_index("ix_call_feedback_user_id", "call_feedback", ["user_id"], unique=False)
    if "ix_call_feedback_seen_call_id" not in indexes:
        op.create_index("ix_call_feedback_seen_call_id", "call_feedback", ["seen_call_id"], unique=False)
    if "ix_call_feedback_user_seen_call_unique" not in indexes:
        op.create_index(
            "ix_call_feedback_user_seen_call_unique",
            "call_feedback",
            ["user_id", "seen_call_id"],
            unique=True,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    tables = set(inspector.get_table_names())
    if "call_feedback" not in tables:
        return
    op.drop_table("call_feedback")
