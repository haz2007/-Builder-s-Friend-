"""Новый товар и фото товара прямо из бота: сфотографировал на складе — отправил.

Диалог из шести шагов: название → раздел → единица → цена → остаток → фото.
Фото сжимается так же, как при загрузке в админке (WebP до 1600 px).
"""

import html
import uuid

import requests

from app.models import Category, Product
from app.routers import products as products_router
from app.services import audit
from app.services.images import BadImage, compress_photo
from app.services.order_notifications import format_money, format_quantity
from app.services.telegram_service import telegram_file_url, telegram_proxies

from .config import TOKEN, logger, user_states
from .context import get_logged_user, require_user, session
from .stock import parse_number, product_screen
from .telegram import HOME_ROW, button, delete_message, inline, show_screen, telegram_request

UNITS = ["шт", "м3", "кг", "лист", "м", "пачка"]
MAX_PHOTO_BYTES = 15 * 1024 * 1024
# Шаги диалога; в них бот ждёт текст или фото
NEW_PRODUCT_STEPS = ("new_name", "new_category", "new_unit", "new_price", "new_stock", "new_photo", "set_photo")

CANCEL_ROW = [button("✖️ Отмена", "a:stock")]


def new_product_prompt(chat_id, telegram_user_id, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    user_states[telegram_user_id] = {"step": "new_name"}
    show_screen(
        chat_id, telegram_user_id,
        "➕ <b>Новый товар</b> · шаг 1 из 6\n\nНапиши название, например «Брус 150×150×6000».",
        inline(CANCEL_ROW), message_id,
    )


def category_prompt(chat_id, telegram_user_id, state: dict):
    with session() as db:
        top = db.query(Category).filter(Category.parent_id.is_(None)).order_by(Category.name).all()
        rows = []
        for parent in top:
            children = parent.children
            if not children:
                rows.append([button(f"📁 {parent.name}", f"a:newcat:{parent.id}")])
            for child in children:
                rows.append([button(f"{parent.name} → {child.name}", f"a:newcat:{child.id}")])
    state["step"] = "new_category"
    show_screen(
        chat_id, telegram_user_id,
        f"➕ <b>{html.escape(state['name'])}</b> · шаг 2 из 6\n\nВ какой раздел?",
        inline(*rows, CANCEL_ROW),
    )


def choose_category(chat_id, telegram_user_id, category_id: int, message_id=None):
    state = user_states.get(telegram_user_id)
    if not state or state.get("step") != "new_category":
        return
    state["category_id"] = category_id
    state["step"] = "new_unit"
    rows = [[button(unit, f"a:newunit:{index}") for index, unit in enumerate(UNITS[:3])],
            [button(unit, f"a:newunit:{index + 3}") for index, unit in enumerate(UNITS[3:])]]
    show_screen(
        chat_id, telegram_user_id,
        f"➕ <b>{html.escape(state['name'])}</b> · шаг 3 из 6\n\nВ чём считается товар на складе?\n"
        "<i>Для доски — «шт»: продажу кубами можно добавить потом в админке.</i>",
        inline(*rows, CANCEL_ROW), message_id,
    )


def choose_unit(chat_id, telegram_user_id, index: int, message_id=None):
    state = user_states.get(telegram_user_id)
    if not state or state.get("step") != "new_unit" or not 0 <= index < len(UNITS):
        return
    state["unit"] = UNITS[index]
    state["step"] = "new_price"
    show_screen(
        chat_id, telegram_user_id,
        f"➕ <b>{html.escape(state['name'])}</b> · шаг 4 из 6\n\nЦена за 1 {state['unit']} в рублях, например 950.",
        inline(CANCEL_ROW), message_id,
    )


def photo_prompt(chat_id, telegram_user_id, state: dict, error: str = ""):
    state["step"] = "new_photo"
    show_screen(
        chat_id, telegram_user_id,
        (f"⚠️ {html.escape(error)}\n\n" if error else "")
        + f"➕ <b>{html.escape(state['name'])}</b> · шаг 6 из 6\n\n"
        f"{format_money(state['price'])} за {state['unit']}, "
        f"остаток {format_quantity(state['stock'])} {state['unit']}.\n\n"
        "📷 Пришли фото товара — или сохрани без фото.",
        inline([button("Сохранить без фото", "a:newsave")], CANCEL_ROW),
    )


def photo_change_prompt(chat_id, telegram_user_id, product_id: int, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    user_states[telegram_user_id] = {"step": "set_photo", "product_id": product_id}
    show_screen(
        chat_id, telegram_user_id,
        "📷 Пришли новое фото товара.",
        inline([button("✖️ Отмена", f"a:prod:{product_id}")]), message_id,
    )


def download_photo(message: dict) -> bytes:
    """Самое большое из присланных фото; картинку, отправленную файлом, тоже берём."""
    if message.get("photo"):
        file_id = message["photo"][-1]["file_id"]
    elif (message.get("document") or {}).get("mime_type", "").startswith("image/"):
        file_id = message["document"]["file_id"]
    else:
        raise BadImage("Это не фото. Пришли снимок товара.")
    info = telegram_request("getFile", {"file_id": file_id})
    if info.get("file_size", 0) > MAX_PHOTO_BYTES:
        raise BadImage("Фото больше 15 МБ.")
    response = requests.get(
        telegram_file_url(TOKEN or "", info["file_path"]), timeout=30, proxies=telegram_proxies()
    )
    response.raise_for_status()
    return response.content


def save_photo(contents: bytes) -> str:
    """Сжимает и кладёт рядом с фото из админки; возвращает адрес для сайта."""
    data = compress_photo(contents)
    folder = products_router.UPLOAD_DIR
    folder.mkdir(parents=True, exist_ok=True)
    filename = f"{uuid.uuid4().hex}.webp"
    (folder / filename).write_bytes(data)
    return f"/uploads/products/{filename}"


def create_product(chat_id, telegram_user_id, image_url: str | None = None):
    state = user_states.pop(telegram_user_id, None)
    if not state or "stock" not in state:
        return
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is None or user.role != "ADMIN":
            show_screen(chat_id, telegram_user_id, "Нужно войти как администратор.", inline(HOME_ROW))
            return
        category = db.get(Category, state["category_id"])
        if category is None:
            show_screen(chat_id, telegram_user_id, "Раздел удалён — начни заново.", inline(HOME_ROW))
            return
        product = Product(
            name=state["name"],
            price=state["price"],
            stock_quantity=state["stock"],
            unit=state["unit"],
            category_id=category.id,
            is_active=1,
            image_url=image_url,
        )
        product.categories = [category]
        db.add(product)
        db.flush()
        audit.record(
            db, user, "product.created", "product", product.id,
            f"Добавлен товар {audit.product_title(product)}: {product.price:g} ₽ за {product.unit}, "
            f"остаток {product.stock_quantity:g} (Telegram)",
        )
        db.commit()
        product_id = product.id
    product_screen(chat_id, telegram_user_id, product_id, title="✅ <b>Товар добавлен и уже в каталоге</b>")


def set_product_photo(chat_id, telegram_user_id, product_id: int, image_url: str):
    user_states.pop(telegram_user_id, None)
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        product = db.get(Product, product_id)
        if user is None or user.role != "ADMIN" or product is None:
            return
        product.image_url = image_url
        audit.record(db, user, "product.photo", "product", product.id,
                     f"{audit.product_title(product)}: новое фото (Telegram)")
        db.commit()
    product_screen(chat_id, telegram_user_id, product_id, title="✅ <b>Фото обновлено</b>")


def handle_new_product_message(message: dict, state: dict) -> None:
    chat_id = message["chat"]["id"]
    telegram_user_id = message["from"]["id"]
    text = (message.get("text") or "").strip()
    delete_message(chat_id, message["message_id"])
    step = state["step"]

    if step == "new_name":
        if not 2 <= len(text) <= 200:
            show_screen(chat_id, telegram_user_id, "Название — от 2 до 200 символов.", inline(CANCEL_ROW))
            return
        state["name"] = " ".join(text.split())
        category_prompt(chat_id, telegram_user_id, state)
        return

    if step in ("new_price", "new_stock"):
        parsed = parse_number(text)
        value = float(parsed[1]) if parsed and parsed[0] == "=" else None
        if step == "new_price":
            if value is None or not 0 < value <= 10_000_000:
                show_screen(chat_id, telegram_user_id, "⚠️ Нужна цена числом, например 950.", inline(CANCEL_ROW))
                return
            state["price"] = round(value, 2)
            state["step"] = "new_stock"
            show_screen(
                chat_id, telegram_user_id,
                f"➕ <b>{html.escape(state['name'])}</b> · шаг 5 из 6\n\n"
                f"Сколько {state['unit']} на складе? Например 120.",
                inline(CANCEL_ROW),
            )
            return
        if value is None or not 0 <= value <= 1_000_000 or (state["unit"] == "шт" and value != int(value)):
            show_screen(chat_id, telegram_user_id, "⚠️ Нужен остаток числом, для штук — целым.", inline(CANCEL_ROW))
            return
        state["stock"] = value
        photo_prompt(chat_id, telegram_user_id, state)
        return

    if step in ("new_photo", "set_photo"):
        try:
            image_url = save_photo(download_photo(message))
        except BadImage as error:
            if step == "new_photo":
                photo_prompt(chat_id, telegram_user_id, state, str(error))
            else:
                show_screen(chat_id, telegram_user_id, f"⚠️ {html.escape(str(error))}",
                            inline([button("✖️ Отмена", f"a:prod:{state['product_id']}")]))
            return
        except Exception:
            logger.exception("Не удалось получить фото из Telegram")
            show_screen(chat_id, telegram_user_id, "⚠️ Не получилось скачать фото — пришли ещё раз.",
                        inline(CANCEL_ROW))
            return
        if step == "new_photo":
            create_product(chat_id, telegram_user_id, image_url)
        else:
            set_product_photo(chat_id, telegram_user_id, state["product_id"], image_url)
