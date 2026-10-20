"""Add parent category (subcategories)

Revision ID: 106a6750d936
Revises: 6b2822adbe21

Подкатегории: «Пиломатериалы → Доска, Брус», «Крепёж → Саморезы».
Глубина — два уровня: у подкатегории не может быть своих подкатегорий.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "106a6750d936"
down_revision: Union[str, Sequence[str], None] = "6b2822adbe21"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "categories",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_categories_parent_id_categories",
        "categories",
        "categories",
        ["parent_id"],
        ["id"],
        ondelete="SET NULL",
    )
    op.create_index("ix_categories_parent_id", "categories", ["parent_id"])


def downgrade() -> None:
    op.drop_index("ix_categories_parent_id", table_name="categories")
    op.drop_constraint(
        "fk_categories_parent_id_categories",
        "categories",
        type_="foreignkey",
    )
    op.drop_column("categories", "parent_id")
