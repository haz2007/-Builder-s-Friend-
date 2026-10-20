"""Add CHECK constraints

Revision ID: d81e5c2a9f63
Revises: c3d9a1f40b27

База сама не даёт записать отрицательный остаток, неизвестный статус
заказа или роль — даже если в коде появится ошибка.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "d81e5c2a9f63"
down_revision: Union[str, Sequence[str], None] = "c3d9a1f40b27"
branch_labels = None
depends_on = None


CHECKS = [
    ("users", "ck_users_role", "role IN ('CUSTOMER', 'ADMIN')"),
    ("products", "ck_products_stock_not_negative", "stock_quantity >= 0"),
    ("products", "ck_products_price_not_negative", "price >= 0"),
    ("product_variants", "ck_product_variants_price_not_negative", "price >= 0"),
    ("product_variants", "ck_product_variants_base_quantity_positive", "base_quantity > 0"),
    (
        "orders",
        "ck_orders_status",
        "status IN ('NEW', 'CONFIRMED', 'PREPARING', 'READY_FOR_DELIVERY', "
        "'ON_THE_WAY', 'DELIVERED', 'CANCELLED')",
    ),
    ("orders", "ck_orders_delivery_method", "delivery_method IN ('DELIVERY', 'PICKUP')"),
    ("orders", "ck_orders_total_not_negative", "total_price >= 0"),
    ("order_items", "ck_order_items_quantity_positive", "quantity > 0"),
    ("order_items", "ck_order_items_price_not_negative", "price >= 0"),
    ("order_items", "ck_order_items_base_quantity_positive", "base_quantity > 0"),
]


def upgrade() -> None:
    for table, name, condition in CHECKS:
        op.create_check_constraint(name, table, condition)


def downgrade() -> None:
    for table, name, _ in reversed(CHECKS):
        op.drop_constraint(name, table, type_="check")
