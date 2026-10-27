"""Add category position

Revision ID: d3e5f7a9b1c4
Revises: c2d4e6f8a0b3

Порядок разделов в магазине: сначала пиломатериалы, потом остальное,
а не по алфавиту. Меньше — выше; по умолчанию 100.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d3e5f7a9b1c4"
down_revision: str | Sequence[str] | None = "c2d4e6f8a0b3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("categories", sa.Column("position", sa.Integer(), nullable=False, server_default="100"))


def downgrade() -> None:
    op.drop_column("categories", "position")
