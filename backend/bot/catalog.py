"""Каталог: разделы и товары с вариантами продажи."""

import html

from app.models import (
    Category,
    Product,
)
from app.routers.categories import category_with_children_ids
from app.services.order_notifications import (
    format_money,
    format_quantity,
)

from .config import PAGE_SIZE
from .context import session
from .telegram import HOME_ROW, button, inline, show_screen


def catalog_screen(chat_id: int, telegram_user_id: int, message_id=None):
    with session() as db:
        categories = (
            db.query(Category)
            .filter(Category.parent_id.is_(None))
            .order_by(Category.name)
            .all()
        )
        rows = [[button(f"📁 {category.name}", f"cat:{category.id}:0")] for category in categories]
    show_screen(
        chat_id,
        telegram_user_id,
        "🛍 <b>Каталог</b>\n\nВыбери категорию. Заказ оформляется на сайте.",
        inline(*rows, HOME_ROW),
        message_id,
    )


def category_screen(chat_id: int, telegram_user_id: int, category_id: int, page: int, message_id=None):
    with session() as db:
        category = db.get(Category, category_id)
        if category is None:
            catalog_screen(chat_id, telegram_user_id, message_id)
            return
        ids = category_with_children_ids(db, category_id)
        subcategory_rows = [
            [button(f"↳ {child.name}", f"cat:{child.id}:0")] for child in category.children
        ]
        back_data = f"cat:{category.parent_id}:0" if category.parent_id else "catalog"
        query = (
            db.query(Product)
            .filter(
                Product.is_active == 1,
                Product.category_id.in_(ids)
                | Product.categories.any(Category.id.in_(ids)),
            )
            .order_by(Product.name)
        )
        total = query.count()
        page = max(0, min(page, max(0, (total - 1) // PAGE_SIZE)))
        products = query.offset(page * PAGE_SIZE).limit(PAGE_SIZE).all()

        lines = [f"📁 <b>{html.escape(category.name)}</b>", ""]
        if not products:
            lines.append("В этой категории пока нет товаров.")
        for product in products:
            lines.append(f"<b>{html.escape(product.name)}</b>")
            for variant in product.variants:
                if variant.is_active != 1:
                    continue
                lines.append(
                    f"  • {html.escape(variant.name)}: {format_money(variant.price)} / "
                    f"{html.escape(variant.unit)} — в наличии "
                    f"{format_quantity(variant.stock_quantity)} {html.escape(variant.unit)}"
                )
            if product.pieces_per_cubic_meter:
                lines.append(f"  <i>В 1 м³ — {product.pieces_per_cubic_meter} шт</i>")
            lines.append("")

    navigation = []
    if page > 0:
        navigation.append(button("◀️", f"cat:{category_id}:{page - 1}"))
    if (page + 1) * PAGE_SIZE < total:
        navigation.append(button("▶️", f"cat:{category_id}:{page + 1}"))
    show_screen(
        chat_id,
        telegram_user_id,
        "\n".join(lines).strip(),
        inline(*subcategory_rows, navigation, [button("◀️ Назад", back_data)], HOME_ROW),
        message_id,
    )
