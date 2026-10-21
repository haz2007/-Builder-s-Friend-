"""Add password reset codes

Revision ID: d6e8f0a2b4c5
Revises: c5d7e9f1a3b4

Одноразовые коды сброса пароля, которые бот присылает в Telegram.
Хранится только хеш кода, у пользователя не больше одного кода.
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "d6e8f0a2b4c5"
down_revision: str | Sequence[str] | None = "c5d7e9f1a3b4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "password_reset_codes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("code_hash", sa.String(255), nullable=False),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.UniqueConstraint("user_id"),
    )


def downgrade() -> None:
    op.drop_table("password_reset_codes")
