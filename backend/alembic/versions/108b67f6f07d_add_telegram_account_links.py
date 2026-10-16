
"""Add Telegram account links

Revision ID: 108b67f6f07d
Revises: b72d1c4a9e31
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "108b67f6f07d"
down_revision: Union[str, Sequence[str], None] = "b72d1c4a9e31"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "telegram_account_links",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "user_id",
            sa.Integer(),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "telegram_user_id",
            sa.BigInteger(),
            nullable=False,
            unique=True,
        ),
        sa.Column(
            "telegram_chat_id",
            sa.BigInteger(),
            nullable=False,
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )


def downgrade() -> None:
    op.drop_table("telegram_account_links")
