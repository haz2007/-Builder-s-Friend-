"""Add order comment

Revision ID: a9b1c3d5e7f9
Revises: f8a0b2c4d6e7

Комментарий покупателя к заказу: распил, время доставки, как проехать.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "a9b1c3d5e7f9"
down_revision: str | Sequence[str] | None = "f8a0b2c4d6e7"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("comment", sa.String(500), nullable=True))


def downgrade() -> None:
    op.drop_column("orders", "comment")
