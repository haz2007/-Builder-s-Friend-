"""Add orders.created_at

Revision ID: b4c6d8e0f2a3
Revises: a3b5c7d9e1f2

Дата заказа раньше вычислялась каждый раз как MIN(created_at) по истории
статусов — лишний подзапрос с GROUP BY в каждом отчёте, и по ней нельзя
построить индекс. Теперь она хранится в заказе; для старых заказов берётся
из истории (первая запись — оформление).
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b4c6d8e0f2a3"
down_revision: Union[str, Sequence[str], None] = "a3b5c7d9e1f2"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("orders", sa.Column("created_at", sa.DateTime(), nullable=True))
    op.execute(
        """
        UPDATE orders AS o
        SET created_at = COALESCE(first_status.created_at, now() AT TIME ZONE 'UTC')
        FROM orders AS src
        LEFT JOIN (
            SELECT order_id, MIN(created_at) AS created_at
            FROM order_status_history
            GROUP BY order_id
        ) AS first_status ON first_status.order_id = src.id
        WHERE src.id = o.id
        """
    )
    op.alter_column("orders", "created_at", nullable=False)


def downgrade() -> None:
    op.drop_column("orders", "created_at")
