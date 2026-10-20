"""Add owner flag to users

Revision ID: 6b2822adbe21
Revises: 7fd8efffa6f4

Владелец магазина — администратор, который может назначать и снимать
других администраторов. Назначается командой:
    python manage.py set-owner <email или телефон>
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "6b2822adbe21"
down_revision: Union[str, Sequence[str], None] = "7fd8efffa6f4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column(
            "is_owner",
            sa.Integer(),
            nullable=False,
            server_default="0",
        ),
    )


def downgrade() -> None:
    op.drop_column("users", "is_owner")
