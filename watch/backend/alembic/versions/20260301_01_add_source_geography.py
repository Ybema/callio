"""add source geography fields and indexes

Revision ID: 20260301_01
Revises:
Create Date: 2026-03-01 21:40:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260301_01"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("sources")}
    indexes = {idx["name"] for idx in inspector.get_indexes("sources")}

    if "origin_country_code" not in columns:
        op.add_column("sources", sa.Column("origin_country_code", sa.String(length=2), nullable=True))
    if "origin_region" not in columns:
        op.add_column("sources", sa.Column("origin_region", sa.String(), nullable=True))

    if "ix_sources_origin_country_code" not in indexes:
        op.create_index("ix_sources_origin_country_code", "sources", ["origin_country_code"], unique=False)
    if "ix_sources_origin_region" not in indexes:
        op.create_index("ix_sources_origin_region", "sources", ["origin_region"], unique=False)
    if "ix_sources_user_country_region" not in indexes:
        op.create_index(
            "ix_sources_user_country_region",
            "sources",
            ["user_id", "origin_country_code", "origin_region"],
            unique=False,
        )


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("sources")}
    indexes = {idx["name"] for idx in inspector.get_indexes("sources")}

    if "ix_sources_user_country_region" in indexes:
        op.drop_index("ix_sources_user_country_region", table_name="sources")
    if "ix_sources_origin_region" in indexes:
        op.drop_index("ix_sources_origin_region", table_name="sources")
    if "ix_sources_origin_country_code" in indexes:
        op.drop_index("ix_sources_origin_country_code", table_name="sources")

    if "origin_region" in columns:
        op.drop_column("sources", "origin_region")
    if "origin_country_code" in columns:
        op.drop_column("sources", "origin_country_code")
