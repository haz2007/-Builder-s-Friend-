"""Add delivery method to orders

Revision ID: 243265877883
Revises: 106a6750d936

DELIVERY — привозит магазин, PICKUP — покупатель забирает сам
(на своей машине или на нанятой).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "243265877883"
down_revision: Union[str, Sequence[str], None] = "106a6750d936"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column(
            "delivery_method",
            sa.String(20),
            nullable=False,
            server_default="DELIVERY",
        ),
    )


def downgrade() -> None:
    op.drop_column("orders", "delivery_method")
