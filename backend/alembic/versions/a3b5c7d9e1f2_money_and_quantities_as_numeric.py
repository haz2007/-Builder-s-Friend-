"""Money and quantities as NUMERIC

Revision ID: a3b5c7d9e1f2
Revises: f2a7c9e1b4d8

float (double precision) хранит 0.1 приблизительно — на суммах заказов это
даёт копеечные погрешности. Деньги — NUMERIC(12, 2), количества и остатки —
NUMERIC(12, 3) (крепёж продаётся на вес, до граммов). Значения округляются
при переводе, CHECK-ограничения продолжают работать.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "a3b5c7d9e1f2"
down_revision: Union[str, Sequence[str], None] = "f2a7c9e1b4d8"
branch_labels = None
depends_on = None


COLUMNS = [
    ("products", "price", 2),
    ("products", "stock_quantity", 3),
    ("product_variants", "price", 2),
    ("product_variants", "base_quantity", 3),
    ("orders", "total_price", 2),
    ("order_items", "price", 2),
    ("order_items", "quantity", 3),
    ("order_items", "base_quantity", 3),
]


def upgrade() -> None:
    for table, column, scale in COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE NUMERIC(12, {scale}) "
            f"USING round({column}::numeric, {scale})"
        )


def downgrade() -> None:
    for table, column, _ in COLUMNS:
        op.execute(
            f"ALTER TABLE {table} ALTER COLUMN {column} TYPE DOUBLE PRECISION "
            f"USING {column}::double precision"
        )
