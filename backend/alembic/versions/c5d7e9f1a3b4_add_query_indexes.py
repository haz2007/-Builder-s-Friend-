"""Add indexes for frequent queries

Revision ID: c5d7e9f1a3b4
Revises: b4c6d8e0f2a3

PostgreSQL не создаёт индексы на внешние ключи сам. Индексы — под реальные
запросы приложения (замеры «до и после» — docs/sql/README.md):
- «Мои заказы» — (user_id, id): фильтр и сортировка ORDER BY id DESC одним индексом;
- позиции и история заказа — по внешним ключам;
- счётчик новых заказов и отчёты — (status, created_at) и created_at;
- колокольчик — непрочитанные уведомления покупателя (user_id, is_read);
- товары категории — products.category_id и product_categories.category_id.
"""

from typing import Sequence, Union

from alembic import op


revision: str = "c5d7e9f1a3b4"
down_revision: Union[str, Sequence[str], None] = "b4c6d8e0f2a3"
branch_labels = None
depends_on = None


INDEXES = [
    ("ix_orders_user_id_id", "orders", ["user_id", "id"]),
    ("ix_orders_created_at", "orders", ["created_at"]),
    ("ix_orders_status_created_at", "orders", ["status", "created_at"]),
    ("ix_order_items_order_id", "order_items", ["order_id"]),
    ("ix_order_items_product_id", "order_items", ["product_id"]),
    ("ix_order_status_history_order_id", "order_status_history", ["order_id"]),
    ("ix_notifications_user_id_is_read", "notifications", ["user_id", "is_read"]),
    ("ix_products_category_id", "products", ["category_id"]),
    ("ix_product_categories_category_id", "product_categories", ["category_id"]),
]


def upgrade() -> None:
    for name, table, columns in INDEXES:
        op.create_index(name, table, columns)


def downgrade() -> None:
    for name, table, _ in reversed(INDEXES):
        op.drop_index(name, table_name=table)
