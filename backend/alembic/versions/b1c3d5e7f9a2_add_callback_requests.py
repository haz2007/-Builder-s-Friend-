"""Add callback requests

Revision ID: b1c3d5e7f9a2
Revises: a9b1c3d5e7f9

Заявки «перезвоните мне»: имя, телефон и корзина — без регистрации.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "b1c3d5e7f9a2"
down_revision: str | Sequence[str] | None = "a9b1c3d5e7f9"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "callback_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("comment", sa.String(500), nullable=True),
        sa.Column("cart_summary", sa.Text(), nullable=True),
        sa.Column("cart_total", sa.Numeric(12, 2), nullable=True),
        sa.Column("status", sa.String(10), nullable=False, server_default="NEW"),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("handled_by_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("handled_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('NEW', 'DONE')", name="ck_callback_requests_status"),
    )
    op.create_index("ix_callback_requests_status_id", "callback_requests", ["status", "id"])


def downgrade() -> None:
    op.drop_index("ix_callback_requests_status_id", table_name="callback_requests")
    op.drop_table("callback_requests")
