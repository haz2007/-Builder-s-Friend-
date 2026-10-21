"""Add trigram search on product names

Revision ID: c2d4e6f8a0b3
Revises: b1c3d5e7f9a2

pg_trgm и GIN-индекс по lower(name): «досака» находит «Доска обрезная».
"""

from collections.abc import Sequence

from alembic import op

revision: str = "c2d4e6f8a0b3"
down_revision: str | Sequence[str] | None = "b1c3d5e7f9a2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.execute("CREATE INDEX ix_products_name_trgm ON products USING gin (lower(name) gin_trgm_ops)")


def downgrade() -> None:
    op.execute("DROP INDEX IF EXISTS ix_products_name_trgm")
