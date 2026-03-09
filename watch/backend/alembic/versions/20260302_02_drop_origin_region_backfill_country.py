"""drop origin_region and backfill country code

Revision ID: 20260302_02
Revises: 20260302_01
Create Date: 2026-03-02 00:25:00.000000
"""

from typing import Sequence, Union
from urllib.parse import urlparse

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "20260302_02"
down_revision: Union[str, Sequence[str], None] = "20260302_01"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _infer_country_code(url: str | None) -> str | None:
    if not url:
        return None
    try:
        host = (urlparse(url).hostname or "").lower()
    except Exception:
        return None
    if not host:
        return None
    tld = host.split(".")[-1]
    if len(tld) == 2 and tld.isalpha():
        return tld.upper()
    return None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("sources")}
    indexes = {idx["name"] for idx in inspector.get_indexes("sources")}

    # Backfill missing country code from URL before dropping region.
    rows = bind.execute(sa.text("SELECT id, url, origin_country_code FROM sources")).mappings().all()
    for row in rows:
        current = (row["origin_country_code"] or "").strip().upper()
        if current:
            continue
        inferred = _infer_country_code(row["url"])
        if inferred:
            bind.execute(
                sa.text("UPDATE sources SET origin_country_code=:country WHERE id=:id"),
                {"country": inferred, "id": row["id"]},
            )

    if "ix_sources_user_country_region" in indexes:
        op.drop_index("ix_sources_user_country_region", table_name="sources")
    if "ix_sources_origin_region" in indexes:
        op.drop_index("ix_sources_origin_region", table_name="sources")
    if "ix_sources_user_country" not in indexes:
        op.create_index("ix_sources_user_country", "sources", ["user_id", "origin_country_code"], unique=False)

    if "origin_region" in columns:
        op.drop_column("sources", "origin_region")


def downgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    columns = {col["name"] for col in inspector.get_columns("sources")}
    indexes = {idx["name"] for idx in inspector.get_indexes("sources")}

    if "origin_region" not in columns:
        op.add_column("sources", sa.Column("origin_region", sa.String(), nullable=True))

    if "ix_sources_user_country" in indexes:
        op.drop_index("ix_sources_user_country", table_name="sources")
    if "ix_sources_origin_region" not in indexes:
        op.create_index("ix_sources_origin_region", "sources", ["origin_region"], unique=False)
    if "ix_sources_user_country_region" not in indexes:
        op.create_index(
            "ix_sources_user_country_region",
            "sources",
            ["user_id", "origin_country_code", "origin_region"],
            unique=False,
        )
