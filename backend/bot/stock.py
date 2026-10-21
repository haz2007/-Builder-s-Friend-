"""Склад в боте: низкие остатки, поиск товара, новый остаток и цена.

Администратор на складе меняет остаток или цену с телефона, не открывая
админку: «+20» — пришла партия, «-3» — списали, «150» — пересчитали.
Изменения попадают в журнал действий так же, как правки на сайте.
"""

import html
import re
from decimal import Decimal, InvalidOperation

from sqlalchemy.orm import selectinload

from app import store_info
from app.models import Product, ProductVariant, User, is_piece_unit
from app.routers.products import search_words
from app.services import audit
from app.services.order_notifications import format_money, format_quantity
from app.services.variant_service import sync_product_from_primary

from .config import LOW_STOCK_LIMIT, user_states
from .context import get_logged_user, require_user, session
from .telegram import HOME_ROW, button, delete_message, inline, show_screen

MAX_STOCK = Decimal("1000000")
MAX_PRICE = Decimal("10000000")
SEARCH_LIMIT = 10
# Шаги диалога, в которых бот ждёт от админа текст
STOCK_STEPS = ("find_product", "set_stock", "set_price")


def parse_number(text: str) -> tuple[str, Decimal] | None:
    """«+20» → ("+", 20), «-3,5» → ("-", 3.5), «1 200» → ("=", 1200)."""
    text = text.strip().replace(" ", "").replace(" ", "").replace(",", ".")
    match = re.fullmatch(r"([+-]?)(\d+(?:\.\d+)?)", text)
    if match is None:
        return None
    try:
        value = Decimal(match.group(2))
    except InvalidOperation:
        return None
    return (match.group(1) or "="), value


def product_button(product: Product) -> list[dict]:
    return [button(
        f"{product.name} · {format_quantity(product.stock_quantity)} {product.unit}",
        f"a:prod:{product.id}",
    )]


def admin_stock_screen(chat_id, telegram_user_id, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    user_states.pop(telegram_user_id, None)
    with session() as db:
        products = (
            db.query(Product)
            .filter(Product.is_active == 1, Product.stock_quantity <= LOW_STOCK_LIMIT)
            .order_by(Product.stock_quantity, Product.id)
            .limit(20)
            .all()
        )
        rows = [product_button(product) for product in products]
    text = (
        f"⚠️ <b>Остаток {LOW_STOCK_LIMIT} и меньше</b>\n\n"
        + ("Нажми на товар, чтобы поменять остаток или цену." if products
           else "Всё в порядке — низких остатков нет.")
    )
    extra = []
    if store_info.YANDEX_MAPS_URL:
        extra.append([{"text": "🗺 Открыть в Яндекс Картах", "url": store_info.YANDEX_MAPS_URL}])
    show_screen(
        chat_id, telegram_user_id, text,
        inline([button("🔎 Найти товар", "a:find")], *rows, *extra, HOME_ROW),
        message_id,
    )


def find_product_prompt(chat_id, telegram_user_id, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    user_states[telegram_user_id] = {"step": "find_product"}
    show_screen(
        chat_id, telegram_user_id,
        "🔎 <b>Поиск товара</b>\n\nНапиши часть названия или размер, например «брус 100х100».",
        inline([button("◀️ К остаткам", "a:stock")]),
        message_id,
    )


def search_results_screen(chat_id, telegram_user_id, query: str):
    with session() as db:
        found = db.query(Product).filter(Product.is_active == 1)
        for word in search_words(query):
            pattern = f"%{word}%"
            found = found.filter(Product.name.ilike(pattern) | Product.description.ilike(pattern))
        products = found.order_by(Product.name).limit(SEARCH_LIMIT + 1).all()
        rows = [product_button(product) for product in products[:SEARCH_LIMIT]]
    if not products:
        text = f"По запросу «{html.escape(query)}» ничего не нашлось. Попробуй другое слово."
    else:
        text = f"🔎 <b>Найдено по запросу «{html.escape(query)}»</b>"
        if len(products) > SEARCH_LIMIT:
            text += f"\n\nПоказаны первые {SEARCH_LIMIT} — уточни запрос."
    # Можно сразу искать ещё раз, не нажимая кнопку
    user_states[telegram_user_id] = {"step": "find_product"}
    show_screen(chat_id, telegram_user_id, text, inline(*rows, [button("◀️ К остаткам", "a:stock")]))


def product_screen(chat_id, telegram_user_id, product_id: int, message_id=None, title: str | None = None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    user_states.pop(telegram_user_id, None)
    with session() as db:
        product = (
            db.query(Product).options(selectinload(Product.variants)).filter(Product.id == product_id).first()
        )
        if product is None:
            show_screen(chat_id, telegram_user_id, "Товар не найден.", inline(HOME_ROW), message_id)
            return
        variants = [variant for variant in product.variants if variant.is_active == 1]
        lines = [title or f"📦 <b>{html.escape(product.name)}</b>", ""]
        if title:
            lines += [f"<b>{html.escape(product.name)}</b>", ""]
        lines.append(f"На складе: <b>{format_quantity(product.stock_quantity)} {html.escape(product.unit)}</b>")
        if product.is_active != 1:
            lines.append("<i>Скрыт из каталога</i>")
        lines += ["", "Цены:"]
        lines += [
            f"• {html.escape(variant.name)} — {format_money(variant.price)} за {html.escape(variant.unit)}"
            for variant in variants
        ]
        rows = [[button("📥 Изменить остаток", f"a:setstock:{product.id}")]]
        rows += [
            [button(f"💰 Цена: {variant.name}", f"a:setprice:{variant.id}")]
            for variant in variants
        ]
    rows += [[button("◀️ К остаткам", "a:stock")], HOME_ROW]
    show_screen(chat_id, telegram_user_id, "\n".join(lines), {"inline_keyboard": rows}, message_id)


def stock_prompt(chat_id, telegram_user_id, product_id: int, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    with session() as db:
        product = db.get(Product, product_id)
        if product is None:
            show_screen(chat_id, telegram_user_id, "Товар не найден.", inline(HOME_ROW), message_id)
            return
        text = (
            f"📥 <b>{html.escape(product.name)}</b>\n"
            f"Сейчас: {format_quantity(product.stock_quantity)} {html.escape(product.unit)}\n\n"
            "Отправь число:\n"
            "• <b>+20</b> — пришла партия\n"
            "• <b>-3</b> — списать\n"
            "• <b>150</b> — новый остаток после пересчёта"
        )
    user_states[telegram_user_id] = {"step": "set_stock", "product_id": product_id}
    show_screen(chat_id, telegram_user_id, text, inline([button("✖️ Отмена", f"a:prod:{product_id}")]), message_id)


def price_prompt(chat_id, telegram_user_id, variant_id: int, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    with session() as db:
        variant = db.get(ProductVariant, variant_id)
        if variant is None:
            show_screen(chat_id, telegram_user_id, "Вариант не найден.", inline(HOME_ROW), message_id)
            return
        product_id = variant.product_id
        text = (
            f"💰 <b>{html.escape(variant.product.name)}</b>, {html.escape(variant.name)}\n"
            f"Сейчас: {format_money(variant.price)} за {html.escape(variant.unit)}\n\n"
            "Отправь новую цену в рублях, например <b>14800</b>."
        )
    user_states[telegram_user_id] = {"step": "set_price", "variant_id": variant_id, "product_id": product_id}
    show_screen(chat_id, telegram_user_id, text, inline([button("✖️ Отмена", f"a:prod:{product_id}")]), message_id)


def change_stock(db, user: User, product_id: int, sign: str, value: Decimal) -> str:
    """Меняет остаток под блокировкой строки — заказ в ту же секунду не потеряется."""
    product = db.query(Product).filter(Product.id == product_id).with_for_update().first()
    if product is None:
        raise ValueError("Товар не найден.")
    old = Decimal(str(product.stock_quantity))
    new = old + value if sign == "+" else old - value if sign == "-" else value
    if new < 0:
        raise ValueError(f"Столько нет: на складе {format_quantity(float(old))} {product.unit}.")
    if new > MAX_STOCK:
        raise ValueError("Слишком большое число — проверь, нет ли лишних нулей.")
    if is_piece_unit(product.unit) and new != new.to_integral_value():
        raise ValueError("Этот товар считается штуками — нужно целое число.")
    product.stock_quantity = float(new)
    audit.record(
        db, user, "product.stock", "product", product.id,
        f"{audit.product_title(product)}: остаток {float(old):g} → {float(new):g} (Telegram)",
        {"stock_quantity": [float(old), float(new)]},
    )
    db.commit()
    return f"✅ Остаток: {float(old):g} → {float(new):g} {html.escape(product.unit)}"


def change_price(db, user: User, variant_id: int, value: Decimal) -> str:
    variant = db.query(ProductVariant).filter(ProductVariant.id == variant_id).with_for_update().first()
    if variant is None:
        raise ValueError("Вариант не найден.")
    if value <= 0 or value > MAX_PRICE:
        raise ValueError("Цена должна быть больше нуля и не больше 10 000 000 ₽.")
    if value != value.quantize(Decimal("0.01")):
        raise ValueError("Не больше двух знаков после запятой.")
    old = variant.price
    variant.price = float(value)
    sync_product_from_primary(variant.product)
    audit.record(
        db, user, "variant.updated", "variant", variant.id,
        f"{audit.variant_title(variant.product, variant)}: цена {old:g} → {float(value):g} (Telegram)",
        {"price": [old, float(value)]},
    )
    db.commit()
    return f"✅ Цена «{html.escape(variant.name)}»: {format_money(old)} → {format_money(float(value))}"


def handle_stock_message(message: dict, state: dict) -> None:
    """Ответ на «Найти товар», «Изменить остаток» или «Цена»."""
    chat_id = message["chat"]["id"]
    telegram_user_id = message["from"]["id"]
    text = (message.get("text") or "").strip()
    delete_message(chat_id, message["message_id"])

    if state["step"] == "find_product":
        if not text or len(text) > 100:
            return
        search_results_screen(chat_id, telegram_user_id, text)
        return

    product_id = state["product_id"]
    parsed = parse_number(text)
    if parsed is None or (state["step"] == "set_price" and parsed[0] != "="):
        hint = "Нужно число, например 14800." if state["step"] == "set_price" else "Нужно число: +20, -3 или 150."
        show_screen(
            chat_id, telegram_user_id, f"⚠️ {hint}\n\nПопробуй ещё раз или нажми «Отмена».",
            inline([button("✖️ Отмена", f"a:prod:{product_id}")]),
        )
        return

    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is None or user.role != "ADMIN":
            user_states.pop(telegram_user_id, None)
            show_screen(chat_id, telegram_user_id, "Нужно войти как администратор.", inline(HOME_ROW))
            return
        try:
            if state["step"] == "set_stock":
                result = change_stock(db, user, product_id, *parsed)
            else:
                result = change_price(db, user, state["variant_id"], parsed[1])
        except ValueError as error:
            db.rollback()
            show_screen(
                chat_id, telegram_user_id, f"⚠️ {html.escape(str(error))}\n\nОтправь другое число.",
                inline([button("✖️ Отмена", f"a:prod:{product_id}")]),
            )
            return

    product_screen(chat_id, telegram_user_id, product_id, title=result)
