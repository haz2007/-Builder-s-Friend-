"""Add telegram outbox

Revision ID: e7f9a1b3c5d6
Revises: d6e8f0a2b4c5

Transactional outbox: сообщения в Telegram записываются в той же транзакции,
что и заказ, и отправляются отдельно с повторами. Раньше уведомление
отправлялось фоновой задачей и терялось, если процесс падал после commit.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "e7f9a1b3c5d6"
down_revision: str | Sequence[str] | None = "d6e8f0a2b4c5"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_outbox",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("chat_id", sa.BigInteger(), nullable=False),
        sa.Column("text", sa.Text(), nullable=False),
        sa.Column("reply_markup", sa.JSON(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("last_error", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(), nullable=False),
        sa.Column("sent_at", sa.DateTime(), nullable=True),
        sa.CheckConstraint("status IN ('pending', 'sent', 'failed')", name="ck_telegram_outbox_status"),
    )
    op.create_index(
        "ix_telegram_outbox_status_next_attempt_at", "telegram_outbox", ["status", "next_attempt_at"]
    )


def downgrade() -> None:
    op.drop_index("ix_telegram_outbox_status_next_attempt_at", table_name="telegram_outbox")
    op.drop_table("telegram_outbox")
