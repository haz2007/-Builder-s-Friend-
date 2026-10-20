"""Add product variants and product categories

Revision ID: b1409121fc81
Revises: 108b67f6f07d

Восстановленная миграция: схема совпадает с уже применённой в базе.
Каждый товар получает вариант по умолчанию (его единица измерения,
цена и остаток), а позиции заказов ссылаются на вариант.
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1409121fc81"
down_revision: Union[str, Sequence[str], None] = "108b67f6f07d"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "product_variants",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(100), nullable=False),
        sa.Column("unit", sa.String(20), nullable=False),
        sa.Column("price", sa.Float(), nullable=False),
        sa.Column(
            "stock_quantity",
            sa.Float(),
            nullable=False,
            server_default="0",
        ),
        sa.Column(
            "is_active",
            sa.Integer(),
            nullable=False,
            server_default="1",
        ),
    )
    op.create_index(
        "ix_product_variants_product_id",
        "product_variants",
        ["product_id"],
    )

    op.create_table(
        "product_categories",
        sa.Column(
            "product_id",
            sa.Integer(),
            sa.ForeignKey("products.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column(
            "category_id",
            sa.Integer(),
            sa.ForeignKey("categories.id", ondelete="CASCADE"),
            primary_key=True,
        ),
    )

    # Вариант по умолчанию для каждого существующего товара.
    op.execute(
        """
        INSERT INTO product_variants
            (product_id, name, unit, price, stock_quantity, is_active)
        SELECT id, unit, unit, price, stock_quantity, 1
        FROM products
        ORDER BY id
        """
    )
    op.execute(
        """
        INSERT INTO product_categories (product_id, category_id)
        SELECT id, category_id FROM products
        """
    )

    op.add_column(
        "order_items",
        sa.Column("variant_id", sa.Integer(), nullable=True),
    )
    op.add_column(
        "order_items",
        sa.Column("unit", sa.String(20), nullable=True),
    )
    op.execute(
        """
        UPDATE order_items AS oi
        SET variant_id = (
                SELECT MIN(pv.id) FROM product_variants AS pv
                WHERE pv.product_id = oi.product_id
            ),
            unit = p.unit
        FROM products AS p
        WHERE p.id = oi.product_id
        """
    )
    op.alter_column("order_items", "variant_id", nullable=False)
    op.alter_column("order_items", "unit", nullable=False)
    op.create_foreign_key(
        "fk_order_items_variant_id_product_variants",
        "order_items",
        "product_variants",
        ["variant_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_order_items_variant_id_product_variants",
        "order_items",
        type_="foreignkey",
    )
    op.drop_column("order_items", "unit")
    op.drop_column("order_items", "variant_id")
    op.drop_table("product_categories")
    op.drop_index(
        "ix_product_variants_product_id",
        table_name="product_variants",
    )
    op.drop_table("product_variants")
