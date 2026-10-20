from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import (
    Order,
    Product,
    ProductVariant,
    is_cubic_unit,
    is_piece_unit,
)


def get_primary_variant(product: Product) -> ProductVariant | None:
    """Основной вариант: первый активный, иначе просто первый."""
    for variant in product.variants:
        if variant.is_active == 1:
            return variant

    return product.variants[0] if product.variants else None


def sync_product_from_primary(product: Product) -> None:
    """Цена товара в каталоге = цена основного варианта (для сортировки)."""
    primary = get_primary_variant(product)

    if primary is not None:
        product.price = primary.price


def recalc_cubic_variants(product: Product) -> None:
    """Для досок с размерами вариант «м³» списывает floor(1 / объём) штук."""
    pieces = product.pieces_per_cubic_meter

    if pieces is None:
        return

    if pieces < 1:
        raise HTTPException(
            status_code=400,
            detail="Доска больше 1 м³ — продавать её кубами нельзя",
        )

    for variant in product.variants:
        if is_cubic_unit(variant.unit):
            variant.base_quantity = pieces


def apply_product_fields_to_primary(
    product: Product,
    price: float | None = None,
    unit: str | None = None,
) -> None:
    """Цена из формы товара относится к основному варианту.

    Единица товара — это единица склада; основной вариант «1 к 1»
    переименовывается вместе с ней.
    """
    primary = get_primary_variant(product)

    if price is not None and primary is not None:
        primary.price = price

    if unit is not None:
        if primary is not None and primary.base_quantity == 1:
            if primary.name == primary.unit:
                primary.name = unit
            primary.unit = unit
        product.unit = unit

    sync_product_from_primary(product)


def requires_whole_quantity(product: Product, variant: ProductVariant) -> bool:
    """Доски, кубы и штучный товар продаются только целым количеством."""
    return (
        product.pieces_per_cubic_meter is not None
        or variant.base_quantity != 1
        or is_piece_unit(variant.unit)
    )


def restore_order_stock(db: Session, order: Order) -> None:
    """Возвращает на склад остатки отменённого заказа."""
    for item in order.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .with_for_update()
            .first()
        )

        if product is not None:
            product.stock_quantity += item.quantity * item.base_quantity
