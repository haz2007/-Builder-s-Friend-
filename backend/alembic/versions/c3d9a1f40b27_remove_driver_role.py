"""Remove driver role and deliveries table

Revision ID: c3d9a1f40b27
Revises: 243265877883

Отдельной роли водителя больше нет: доставку делает сам магазин,
поэтому этап «Водитель назначен» убран — после «Готов к доставке»
сразу идёт «В пути». Таблица deliveries нигде не использовалась.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c3d9a1f40b27"
down_revision: Union[str, Sequence[str], None] = "243265877883"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Заказы, застрявшие на убранном этапе, возвращаются на предыдущий
    op.execute(
        "UPDATE orders SET status = 'READY_FOR_DELIVERY' "
        "WHERE status = 'ASSIGNED_TO_DRIVER'"
    )
    op.execute("UPDATE users SET role = 'CUSTOMER' WHERE role = 'DRIVER'")
    op.drop_table("deliveries")


def downgrade() -> None:
    op.create_table(
        "deliveries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("status", sa.String(50), nullable=False),
        sa.Column("address", sa.String(500), nullable=False),
        sa.Column(
            "order_id",
            sa.Integer(),
            sa.ForeignKey("orders.id"),
            nullable=False,
            unique=True,
        ),
        sa.Column("driver_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
    )
