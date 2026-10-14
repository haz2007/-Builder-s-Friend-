
"""Add customer name to orders

Revision ID: b72d1c4a9e31
Revises: 00b3cf7f0b02
Create Date: 2026-10-14
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b72d1c4a9e31"
down_revision: Union[str, Sequence[str], None] = "00b3cf7f0b02"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "orders",
        sa.Column("customer_name", sa.String(length=255), nullable=True),
    )

    op.execute(
        "UPDATE orders SET customer_name = 'Покупатель' "
        "WHERE customer_name IS NULL"
    )

    op.alter_column(
        "orders",
        "customer_name",
        existing_type=sa.String(length=255),
        nullable=False,
    )


def downgrade() -> None:
    op.drop_column("orders", "customer_name")
