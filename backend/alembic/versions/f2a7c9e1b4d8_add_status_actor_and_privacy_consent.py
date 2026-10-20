"""Add status change actor and privacy consent

Revision ID: f2a7c9e1b4d8
Revises: d81e5c2a9f63

- order_status_history.changed_by_id — кто сменил статус (журнал действий);
  у старых записей пусто
- users.privacy_accepted_at — когда покупатель согласился с политикой
  конфиденциальности при регистрации (152-ФЗ)
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f2a7c9e1b4d8"
down_revision: Union[str, Sequence[str], None] = "d81e5c2a9f63"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "order_status_history",
        sa.Column("changed_by_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "order_status_history_changed_by_id_fkey",
        "order_status_history",
        "users",
        ["changed_by_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index(
        "ix_order_status_history_changed_by_id",
        "order_status_history",
        ["changed_by_id"],
    )
    op.add_column(
        "users",
        sa.Column("privacy_accepted_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("users", "privacy_accepted_at")
    op.drop_index("ix_order_status_history_changed_by_id", "order_status_history")
    op.drop_constraint(
        "order_status_history_changed_by_id_fkey", "order_status_history", type_="foreignkey"
    )
    op.drop_column("order_status_history", "changed_by_id")
