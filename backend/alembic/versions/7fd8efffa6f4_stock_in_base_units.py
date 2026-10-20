"""Stock in base units, board dimensions, variant conversion factor

Revision ID: 7fd8efffa6f4
Revises: b1409121fc81

Остаток теперь хранится в товаре в базовой единице (для досок — в
штуках). Вариант продажи списывает base_quantity базовых единиц:
«Штука» = 1, «м³» = floor(1 / объём доски), например 27.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "7fd8efffa6f4"
down_revision: Union[str, Sequence[str], None] = "b1409121fc81"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("products", sa.Column("thickness_mm", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("width_mm", sa.Float(), nullable=True))
    op.add_column("products", sa.Column("length_mm", sa.Float(), nullable=True))

    op.add_column(
        "product_variants",
        sa.Column(
            "base_quantity",
            sa.Float(),
            nullable=False,
            server_default="1",
        ),
    )
    op.add_column(
        "order_items",
        sa.Column(
            "base_quantity",
            sa.Float(),
            nullable=False,
            server_default="1",
        ),
    )

    # products.stock_quantity уже совпадает с остатком основного варианта —
    # он и становится общим складом товара.
    op.drop_column("product_variants", "stock_quantity")


def downgrade() -> None:
    op.add_column(
        "product_variants",
        sa.Column(
            "stock_quantity",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
    )
    op.execute(
        """
        UPDATE product_variants AS pv
        SET stock_quantity = FLOOR(p.stock_quantity / pv.base_quantity)
        FROM products AS p
        WHERE p.id = pv.product_id
        """
    )
    op.drop_column("order_items", "base_quantity")
    op.drop_column("product_variants", "base_quantity")
    op.drop_column("products", "length_mm")
    op.drop_column("products", "width_mm")
    op.drop_column("products", "thickness_mm")
