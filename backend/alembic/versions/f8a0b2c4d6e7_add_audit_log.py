"""Add audit log

Revision ID: f8a0b2c4d6e7
Revises: e7f9a1b3c5d6

Журнал действий в админке: товары, варианты, категории, администраторы,
сброс паролей. Статусы заказов по-прежнему пишутся в order_status_history.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "f8a0b2c4d6e7"
down_revision: str | Sequence[str] | None = "e7f9a1b3c5d6"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("actor_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("action", sa.String(50), nullable=False),
        sa.Column("entity", sa.String(30), nullable=False),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("summary", sa.String(500), nullable=False),
        sa.Column("changes", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
    )
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])
    op.create_index("ix_audit_log_entity", "audit_log", ["entity", "entity_id"])


def downgrade() -> None:
    op.drop_index("ix_audit_log_entity", table_name="audit_log")
    op.drop_index("ix_audit_log_created_at", table_name="audit_log")
    op.drop_table("audit_log")
