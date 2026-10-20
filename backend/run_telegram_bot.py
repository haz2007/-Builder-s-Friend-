"""Telegram-бот магазина «Друг Строителя».

Запуск: .venv/bin/python run_telegram_bot.py (long polling).

Роли:
- гость: каталог и вход;
- покупатель: личный кабинет — заказы, отмена нового заказа,
  уведомления, профиль;
- администратор: заказы с фильтрами и сменой статуса, сводка, остатки;
- владелец: дополнительно назначает и снимает администраторов.

Уведомления о заказах рассылает app/services/order_notifications.py:
пока аккаунт привязан к боту — сообщения приходят, после «Выйти» — нет.
"""

import html
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timedelta, timezone

import requests
from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import func

from app.auth import find_user_by_email, find_user_by_phone, verify_password
from app.database import SessionLocal
from app.rate_limit import telegram_login_limiter, wait_text
from app import store_info
from app.routers.categories import category_with_children_ids
from app.models import (
    Category,
    Notification,
    Order,
    OrderStatusHistory,
    Product,
    TelegramAccountLink,
    User,
)
from app.services.admin_service import (
    AdminServiceError,
    add_admin,
    has_telegram,
    list_admins,
    remove_admin,
)
from app.services.order_notifications import (
    build_customer_message,
    build_order_keyboard,
    build_order_message,
    format_money,
    format_quantity,
    load_order,
    notify_order_cancelled_by_customer,
    notify_order_status_changed,
    status_name,
)
from app.services.telegram_service import telegram_api_url, telegram_proxies
from app.services.order_service import (
    allowed_transitions,
    change_order_status,
    get_status_value,
)
from app.services.variant_service import restore_order_stock

load_dotenv()

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)
# requests/urllib3 не должны писать URL с токеном в лог
logging.getLogger("urllib3").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = telegram_api_url(TOKEN) if TOKEN else ""

PAGE_SIZE = 5
LOW_STOCK_LIMIT = 10

# Ожидаемый ввод пользователя: вход (логин → пароль) или добавление админа
user_states: dict[int, dict] = {}
# Последний «экран» бота у пользователя: (chat_id, message_id)
screen_messages: dict[int, tuple[int, int]] = {}

ORDER_FILTERS = {
    "new": ("🆕 Новые", ["NEW"]),
    "work": (
        "🔄 В работе",
        ["CONFIRMED", "PREPARING", "READY_FOR_DELIVERY", "ON_THE_WAY"],
    ),
    "done": ("✅ Завершённые", ["DELIVERED", "CANCELLED"]),
    "all": ("📋 Все", None),
}

ROLE_NAMES = {
    "CUSTOMER": "покупатель",
    "ADMIN": "администратор",
}


# ---------------------------------------------------------------- Telegram API


def telegram_request(method: str, payload: dict) -> dict:
    response = requests.post(
        f"{API_URL}/{method}", json=payload, timeout=35, proxies=telegram_proxies()
    )
    try:
        result = response.json()
    except ValueError:
        response.raise_for_status()
        raise RuntimeError("Telegram API returned a non-JSON response")
    if response.status_code >= 400 or not result.get("ok"):
        description = result.get("description", response.reason)
        raise RuntimeError(f"Telegram API error in {method}: {description}")
    return result["result"]


def send_message(chat_id: int, text: str, keyboard=None) -> dict:
    payload = {"chat_id": chat_id, "text": text, "parse_mode": "HTML"}
    if keyboard is not None:
        payload["reply_markup"] = keyboard
    return telegram_request("sendMessage", payload)


def edit_message(chat_id: int, message_id: int, text: str, keyboard=None):
    payload = {
        "chat_id": chat_id,
        "message_id": message_id,
        "text": text,
        "parse_mode": "HTML",
    }
    if keyboard is not None:
        payload["reply_markup"] = keyboard
    return telegram_request("editMessageText", payload)


def delete_message(chat_id: int, message_id: int) -> None:
    try:
        telegram_request("deleteMessage", {"chat_id": chat_id, "message_id": message_id})
    except Exception:
        logger.debug("Не удалось удалить сообщение %s", message_id, exc_info=True)


def answer_callback(callback_id: str, text: str = "", alert=False) -> None:
    try:
        telegram_request(
            "answerCallbackQuery",
            {"callback_query_id": callback_id, "text": text, "show_alert": alert},
        )
    except Exception:
        logger.exception("Не удалось ответить на нажатие кнопки")


def show_screen(
    chat_id: int,
    telegram_user_id: int,
    text: str,
    keyboard=None,
    message_id: int | None = None,
):
    """Редактирует текущий экран, если можно, иначе отправляет новый.

    Обычное меню (reply keyboard) нельзя прикрепить при редактировании,
    поэтому такие экраны всегда отправляются новым сообщением.
    """
    is_inline = keyboard is None or "inline_keyboard" in keyboard
    target = message_id
    if target is None:
        old = screen_messages.get(telegram_user_id)
        if old and old[0] == chat_id:
            target = old[1]

    if target is not None and is_inline:
        try:
            edit_message(chat_id, target, text, keyboard)
            screen_messages[telegram_user_id] = (chat_id, target)
            return target
        except Exception as exc:
            if "message is not modified" in str(exc):
                return target
            logger.info("Не получилось отредактировать экран (%s); отправляю новый", exc)

    sent = send_message(chat_id, text, keyboard)
    new_id = sent["message_id"]
    old = screen_messages.get(telegram_user_id)
    screen_messages[telegram_user_id] = (chat_id, new_id)
    if old and old[0] == chat_id and old[1] != new_id:
        delete_message(chat_id, old[1])
    return new_id


def inline(*rows) -> dict:
    return {"inline_keyboard": [list(row) for row in rows if row]}


def button(text: str, data: str) -> dict:
    return {"text": text, "callback_data": data}


HOME_ROW = [button("🏠 Главное меню", "home")]


# ---------------------------------------------------------------- База и роли


@contextmanager
def session():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_link(db, telegram_user_id: int):
    return db.query(TelegramAccountLink).filter(
        TelegramAccountLink.telegram_user_id == telegram_user_id
    ).first()


def get_logged_user(db, telegram_user_id: int) -> User | None:
    link = get_link(db, telegram_user_id)
    if link is None:
        return None
    return db.query(User).filter(User.id == link.user_id).first()


def main_keyboard(user: User | None = None) -> dict:
    if user is None:
        rows = [["🔑 Войти"], ["🛍 Каталог", "📞 Контакты"]]
    elif user.role == "ADMIN":
        rows = [["📋 Заказы", "📊 Сводка"], ["⚠️ Остатки", "🛍 Каталог"]]
        if user.is_owner == 1:
            rows.append(["👥 Администраторы", "👤 Профиль"])
        else:
            rows.append(["📞 Контакты", "👤 Профиль"])
    else:
        rows = [["📦 Мои заказы", "🔔 Уведомления"], ["🛍 Каталог", "📞 Контакты"], ["👤 Профиль"]]
    return {
        "keyboard": [[{"text": text} for text in row] for row in rows],
        "resize_keyboard": True,
        "is_persistent": True,
    }


def format_date(value: datetime | None) -> str:
    if value is None:
        return ""
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    # Время магазина — Москва (UTC+3)
    return value.astimezone(timezone(timedelta(hours=3))).strftime("%d.%m.%Y %H:%M")


def require_user(chat_id, telegram_user_id, roles: set[str], message_id=None):
    """Возвращает id пользователя с нужной ролью или показывает подсказку."""
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is not None and user.role in roles:
            return user.id
    show_screen(
        chat_id,
        telegram_user_id,
        "🔒 Этот раздел доступен после входа в аккаунт с нужными правами.",
        inline(HOME_ROW),
        message_id,
    )
    return None


# ---------------------------------------------------------------- Общие экраны


def home_screen(chat_id: int, telegram_user_id: int):
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is None:
            text = (
                "👋 <b>Добро пожаловать в «Друг Строителя»!</b>\n\n"
                f"Семейный магазин пиломатериалов — {store_info.YEARS_ON_MARKET} лет на рынке. "
                "Доска, брус, вагонка, крепёж и листовые материалы — поштучно и кубами.\n\n"
                "<b>Что умеет бот:</b>\n"
                "🛍 показать каталог с ценами и остатками\n"
                "📦 показать ваши заказы и их статус\n"
                "🔔 присылать уведомления, когда заказ подтвердят, соберут и отправят\n"
                "📞 подсказать телефоны и адрес склада\n\n"
                "Чтобы видеть свои заказы, нажмите <b>«🔑 Войти»</b> и введите "
                "телефон и пароль от сайта."
            )
        else:
            name = user.phone or user.email
            text = (
                "🌲 <b>Друг Строителя</b>\n\n"
                f"Ты вошёл как <b>{html.escape(name or '')}</b> "
                f"({ROLE_NAMES.get(user.role, user.role)}"
                f"{', владелец' if user.is_owner == 1 else ''}).\n\n"
                "Выбери раздел в меню ниже."
            )
        keyboard = main_keyboard(user)
    show_screen(chat_id, telegram_user_id, text, keyboard)


def profile_screen(chat_id: int, telegram_user_id: int, message_id=None):
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is None:
            show_screen(chat_id, telegram_user_id, "Ты не вошёл в аккаунт.", main_keyboard())
            return
        orders_count = db.query(Order).filter(Order.user_id == user.id).count()
        lines = [
            "👤 <b>Профиль</b>",
            "",
            f"Телефон: {html.escape(user.phone or '—')}",
            f"Email: {html.escape(user.email or '—')}",
            f"Роль: {ROLE_NAMES.get(user.role, user.role)}"
            f"{' (владелец магазина)' if user.is_owner == 1 else ''}",
        ]
        if user.role == "CUSTOMER":
            lines.append(f"Заказов: {orders_count}")
        lines += [
            "",
            "Пока аккаунт привязан к этому Telegram, сюда приходят уведомления "
            "о заказах. После выхода уведомления приходить перестанут.",
        ]
    show_screen(
        chat_id,
        telegram_user_id,
        "\n".join(lines),
        inline([button("🔓 Выйти из аккаунта", "logout")], HOME_ROW),
        message_id,
    )


def logout(chat_id: int, telegram_user_id: int):
    with session() as db:
        link = get_link(db, telegram_user_id)
        if link:
            db.delete(link)
            db.commit()
    user_states.pop(telegram_user_id, None)
    show_screen(
        chat_id,
        telegram_user_id,
        "Ты вышел из аккаунта. Уведомления о заказах больше не будут приходить.",
        main_keyboard(),
    )


def contacts_screen(chat_id: int, telegram_user_id: int, message_id=None):
    lines = [
        f"📞 <b>{store_info.STORE_NAME}</b>",
        "",
        *[f"☎️ {phone}" for phone in store_info.PHONES],
        f"🕘 {store_info.WORKING_HOURS}",
    ]
    if store_info.ADDRESS:
        lines.append(f"📍 {html.escape(store_info.ADDRESS)}")
    lines += [
        "",
        "🚚 Привезём на объект своим транспортом или отгрузим на вашу машину.",
    ]
    rows = []
    if store_info.YANDEX_MAPS_URL:
        rows.append([{"text": "🗺 Открыть в Яндекс Картах", "url": store_info.YANDEX_MAPS_URL}])
    show_screen(chat_id, telegram_user_id, "\n".join(lines), inline(*rows, HOME_ROW), message_id)

    # Точка на карте — отдельным сообщением, по нему можно построить маршрут
    if store_info.LATITUDE and store_info.LONGITUDE:
        try:
            telegram_request("sendVenue", {
                "chat_id": chat_id,
                "latitude": store_info.LATITUDE,
                "longitude": store_info.LONGITUDE,
                "title": store_info.STORE_NAME,
                "address": store_info.ADDRESS or "",
            })
        except Exception:
            logger.exception("Не удалось отправить точку на карте")


def help_screen(chat_id: int, telegram_user_id: int, message_id=None):
    commands = "\n".join(f"/{name} — {title}" for name, title in store_info.BOT_COMMANDS)
    show_screen(
        chat_id,
        telegram_user_id,
        "ℹ️ <b>Что умеет бот</b>\n\n"
        f"{commands}\n\n"
        "Заказ оформляется на сайте, а здесь видно его статус. "
        "Пока вы вошли в аккаунт, уведомления о заказах приходят в этот чат.",
        inline(HOME_ROW),
        message_id,
    )


def setup_bot_profile() -> None:
    """Описание, короткое описание и меню команд — из кода, без ручной настройки."""
    for method, payload in (
        ("setMyDescription", {"description": store_info.BOT_DESCRIPTION}),
        ("setMyShortDescription", {"short_description": store_info.BOT_SHORT_DESCRIPTION}),
        ("setMyCommands", {"commands": [
            {"command": name, "description": title}
            for name, title in store_info.BOT_COMMANDS
        ]}),
    ):
        try:
            telegram_request(method, payload)
        except Exception:
            logger.exception("Не удалось выполнить %s", method)


# ---------------------------------------------------------------- Вход


def login_prompt(chat_id: int, telegram_user_id: int):
    user_states[telegram_user_id] = {"step": "login"}
    show_screen(
        chat_id,
        telegram_user_id,
        "🔐 <b>Вход</b>\n\n"
        "Отправь номер телефона (или email администратора), "
        "указанный на сайте. Следующим сообщением — пароль.\n\n"
        "Для отмены отправь /cancel.",
        inline([button("✖️ Отмена", "home")]),
    )


def handle_login_message(message: dict, state: dict) -> None:
    chat_id = message["chat"]["id"]
    telegram_user_id = message["from"]["id"]
    text = (message.get("text") or "").strip()

    if state["step"] == "login":
        delete_message(chat_id, message["message_id"])
        if not text or len(text) > 255:
            show_screen(chat_id, telegram_user_id, "Введи телефон или email.", inline(HOME_ROW))
            return
        state["login"] = text
        state["step"] = "password"
        show_screen(
            chat_id,
            telegram_user_id,
            "🔑 <b>Теперь отправь пароль</b>\n\nСообщение с паролем бот сразу удалит.",
            inline([button("✖️ Отмена", "home")]),
        )
        return

    # Шаг пароля
    delete_message(chat_id, message["message_id"])
    user_states.pop(telegram_user_id, None)
    login = state.get("login", "")

    retry_after = telegram_login_limiter.hit(str(telegram_user_id))
    if retry_after is not None:
        show_screen(
            chat_id,
            telegram_user_id,
            f"⏳ <b>Слишком много попыток входа</b>\n\nПопробуй через {wait_text(retry_after)}.",
            inline(HOME_ROW),
        )
        return

    with session() as db:
        try:
            user = find_user_by_email(db, login) if "@" in login else find_user_by_phone(db, login)

            if user is None or not verify_password(text, user.password_hash):
                logger.info(
                    "Вход в Telegram не удался (tg_user=%s): %s",
                    telegram_user_id,
                    "аккаунт не найден" if user is None else "неверный пароль",
                )
                show_screen(
                    chat_id,
                    telegram_user_id,
                    "❌ <b>Не удалось войти</b>\n\nПроверь телефон/email и пароль.",
                    inline([button("🔁 Попробовать снова", "login")], HOME_ROW),
                )
                return

            by_user = db.query(TelegramAccountLink).filter(
                TelegramAccountLink.user_id == user.id
            ).first()
            by_telegram = get_link(db, telegram_user_id)

            # Один Telegram — один аккаунт сайта. Старую привязку этого
            # Telegram заменяем, чужую привязку аккаунта — переносим сюда.
            if by_telegram and by_telegram.user_id != user.id:
                db.delete(by_telegram)
            if by_user is None:
                db.add(TelegramAccountLink(
                    user_id=user.id,
                    telegram_user_id=telegram_user_id,
                    telegram_chat_id=chat_id,
                ))
            else:
                by_user.telegram_user_id = telegram_user_id
                by_user.telegram_chat_id = chat_id
            db.commit()
            logger.info("Вход в Telegram: пользователь №%s", user.id)
        except Exception:
            db.rollback()
            logger.exception("Ошибка входа в Telegram")
            show_screen(chat_id, telegram_user_id, "⚠️ Техническая ошибка при входе.", inline(HOME_ROW))
            return

    home_screen(chat_id, telegram_user_id)


# ---------------------------------------------------------------- Каталог


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


# ---------------------------------------------------------------- Покупатель


def customer_orders_screen(chat_id, telegram_user_id, page=0, message_id=None):
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return
    with session() as db:
        query = db.query(Order).filter(Order.user_id == user_id)
        total = query.count()
        if total == 0:
            show_screen(
                chat_id, telegram_user_id,
                "📦 <b>Мои заказы</b>\n\nЗаказов пока нет — оформи первый на сайте.",
                inline(HOME_ROW), message_id,
            )
            return
        max_page = (total - 1) // PAGE_SIZE
        page = max(0, min(page, max_page))
        orders = query.order_by(Order.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE).all()
        rows = [
            [button(
                f"№{order.id} · {status_name(order.status, order.delivery_method)} · {format_money(order.total_price)}",
                f"c:order:{order.id}:{page}",
            )]
            for order in orders
        ]
    navigation = []
    if page > 0:
        navigation.append(button("◀️ Назад", f"c:orders:{page - 1}"))
    if page < max_page:
        navigation.append(button("Вперёд ▶️", f"c:orders:{page + 1}"))
    show_screen(
        chat_id, telegram_user_id,
        f"📦 <b>Мои заказы</b>\n\nВсего: {total} · страница {page + 1} из {max_page + 1}",
        inline(*rows, navigation, HOME_ROW),
        message_id,
    )


def status_history_lines(db, order: Order, show_actor: bool = False) -> list[str]:
    """История статусов; администратору — ещё и кто менял статус."""
    history = (
        db.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == order.id)
        .order_by(OrderStatusHistory.id)
        .all()
    )
    if not history:
        return []
    lines = []
    for entry in history:
        line = f"  {format_date(entry.created_at)} — {status_name(entry.status, order.delivery_method)}"
        if show_actor and entry.changed_by_label:
            line += f" · {html.escape(entry.changed_by_label)}"
        lines.append(line)
    return ["", "🕓 <b>История:</b>"] + lines


def customer_order_screen(chat_id, telegram_user_id, order_id, back_page=0, message_id=None):
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return
    with session() as db:
        order = load_order(db, order_id)
        if order is None or order.user_id != user_id:
            show_screen(chat_id, telegram_user_id, "Заказ не найден.", inline(HOME_ROW), message_id)
            return
        text = "\n".join(
            [build_customer_message(order, f"📦 Заказ №{order.id}")]
            + status_history_lines(db, order)
        )
        can_cancel = get_status_value(order.status) == "NEW"
        delivered = get_status_value(order.status) == "DELIVERED"
    rows = []
    if can_cancel:
        rows.append([button("❌ Отменить заказ", f"c:cancel:{order_id}")])
    if delivered and store_info.YANDEX_REVIEW_URL:
        rows.append([{"text": "⭐ Оставить отзыв на Яндекс Картах", "url": store_info.YANDEX_REVIEW_URL}])
    rows.append([button("◀️ К заказам", f"c:orders:{back_page}")])
    show_screen(chat_id, telegram_user_id, text, inline(*rows, HOME_ROW), message_id)


def customer_cancel_confirm(chat_id, telegram_user_id, order_id, message_id=None):
    show_screen(
        chat_id, telegram_user_id,
        f"Точно отменить заказ №{order_id}? Товар вернётся на склад.",
        inline(
            [button("Да, отменить", f"c:cancelok:{order_id}")],
            [button("Нет, оставить", f"c:order:{order_id}:0")],
        ),
        message_id,
    )


def customer_cancel(chat_id, telegram_user_id, order_id, message_id=None) -> str:
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return ""
    with session() as db:
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if order is None or order.user_id != user_id:
            return "Заказ не найден."
        if get_status_value(order.status) != "NEW":
            return "Отменить можно только новый заказ — позвони в магазин."
        try:
            change_order_status(order, "CANCELLED", db, user_id)
            restore_order_stock(db, order)
            db.commit()
        except HTTPException as error:
            db.rollback()
            return str(error.detail)
    notify_order_cancelled_by_customer(order_id)
    customer_order_screen(chat_id, telegram_user_id, order_id, 0, message_id)
    return f"Заказ №{order_id} отменён"


def customer_notifications_screen(chat_id, telegram_user_id, message_id=None):
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return
    with session() as db:
        notifications = (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.id.desc())
            .limit(10)
            .all()
        )
        unread = db.query(Notification).filter(
            Notification.user_id == user_id, Notification.is_read == 0
        ).count()
        lines = ["🔔 <b>Уведомления</b>", ""]
        if not notifications:
            lines.append("Уведомлений пока нет.")
        for notification in notifications:
            marker = "🔵" if notification.is_read == 0 else "⚪️"
            lines.append(
                f"{marker} {format_date(notification.created_at)} · заказ №{notification.order_id}\n"
                f"    {html.escape(notification.message)}"
            )
    rows = []
    if unread:
        rows.append([button(f"✔️ Отметить прочитанными ({unread})", "n:readall")])
    show_screen(chat_id, telegram_user_id, "\n".join(lines), inline(*rows, HOME_ROW), message_id)


def mark_notifications_read(chat_id, telegram_user_id, message_id=None):
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return
    with session() as db:
        db.query(Notification).filter(
            Notification.user_id == user_id, Notification.is_read == 0
        ).update({"is_read": 1})
        db.commit()
    customer_notifications_screen(chat_id, telegram_user_id, message_id)


# ---------------------------------------------------------------- Администратор


def admin_orders_screen(chat_id, telegram_user_id, filter_key="new", page=0, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    filter_key = filter_key if filter_key in ORDER_FILTERS else "new"
    title, statuses = ORDER_FILTERS[filter_key]
    with session() as db:
        query = db.query(Order)
        if statuses is not None:
            query = query.filter(Order.status.in_(statuses))
        total = query.count()
        max_page = max(0, (total - 1) // PAGE_SIZE)
        page = max(0, min(page, max_page))
        orders = query.order_by(Order.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE).all()
        rows = [
            [button(
                f"№{order.id} · {status_name(order.status, order.delivery_method)} · {format_money(order.total_price)}",
                f"a:order:{order.id}:{filter_key}",
            )]
            for order in orders
        ]
    filters_row = [
        button(("• " if key == filter_key else "") + label.split(" ", 1)[1], f"a:orders:{key}:0")
        for key, (label, _) in ORDER_FILTERS.items()
    ]
    navigation = []
    if page > 0:
        navigation.append(button("◀️ Назад", f"a:orders:{filter_key}:{page - 1}"))
    if page < max_page:
        navigation.append(button("Вперёд ▶️", f"a:orders:{filter_key}:{page + 1}"))
    text = (
        f"📋 <b>Заказы — {title}</b>\n\n"
        + (f"Найдено: {total} · страница {page + 1} из {max_page + 1}" if total else "Заказов нет.")
    )
    show_screen(chat_id, telegram_user_id, text, inline(filters_row, *rows, navigation, HOME_ROW), message_id)


def admin_order_screen(chat_id, telegram_user_id, order_id, filter_key="new", message_id=None, title=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    with session() as db:
        order = load_order(db, order_id)
        if order is None:
            show_screen(chat_id, telegram_user_id, "Заказ не найден.", inline(HOME_ROW), message_id)
            return
        text = "\n".join(
            [build_order_message(order, title or f"📦 Заказ №{order.id}")]
            + status_history_lines(db, order, show_actor=True)
        )
        keyboard = build_order_keyboard(order.id, order.status, order.delivery_method) or {"inline_keyboard": []}
    rows = keyboard["inline_keyboard"]
    rows.append([button("◀️ К заказам", f"a:orders:{filter_key}:0")])
    rows.append(HOME_ROW)
    show_screen(chat_id, telegram_user_id, text, {"inline_keyboard": rows}, message_id)


def admin_change_status(chat_id, telegram_user_id, order_id, new_status, message_id=None) -> str:
    """Кнопки статуса есть и в уведомлениях, и в карточке заказа."""
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is None or user.role != "ADMIN":
            return "Нужно войти как администратор."
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if order is None:
            return "Заказ не найден."
        previous_status = get_status_value(order.status)
        delivery_method = order.delivery_method
        if new_status not in allowed_transitions(previous_status, delivery_method):
            return "Статус уже изменён — обнови карточку заказа."
        try:
            change_order_status(order, new_status, db, user.id)
            if new_status == "CANCELLED":
                restore_order_stock(db, order)
            db.commit()
        except HTTPException as error:
            db.rollback()
            return str(error.detail)
        actor_id = user.id

    notify_order_status_changed(order_id, previous_status, new_status, actor_id)
    admin_order_screen(
        chat_id, telegram_user_id, order_id, "all", message_id,
        title=f"✅ Заказ №{order_id}: {status_name(new_status, delivery_method)}",
    )
    return f"Заказ №{order_id}: {status_name(new_status, delivery_method)}"


def admin_summary_screen(chat_id, telegram_user_id, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    now = datetime.now(timezone.utc)
    today_start = now.astimezone(timezone(timedelta(hours=3))).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).astimezone(timezone.utc).replace(tzinfo=None)
    month_start = (now - timedelta(days=30)).replace(tzinfo=None)

    with session() as db:
        created = (
            db.query(OrderStatusHistory.order_id, func.min(OrderStatusHistory.created_at).label("created_at"))
            .group_by(OrderStatusHistory.order_id)
            .subquery()
        )

        def period_stats(start):
            rows = (
                db.query(Order.status, Order.total_price)
                .join(created, created.c.order_id == Order.id)
                .filter(created.c.created_at >= start)
                .all()
            )
            active = [row for row in rows if row.status != "CANCELLED"]
            return len(rows), sum(row.total_price for row in active)

        today_count, today_sum = period_stats(today_start)
        month_count, month_sum = period_stats(month_start)
        new_count = db.query(Order).filter(Order.status == "NEW").count()
        in_work = db.query(Order).filter(Order.status.in_(ORDER_FILTERS["work"][1])).count()
        low_stock = db.query(Product).filter(
            Product.is_active == 1, Product.stock_quantity <= LOW_STOCK_LIMIT
        ).count()

    text = (
        "📊 <b>Сводка</b>\n\n"
        f"Сегодня: {today_count} заказ(ов) на {format_money(today_sum)}\n"
        f"За 30 дней: {month_count} заказ(ов) на {format_money(month_sum)}\n"
        "<i>(сумма без отменённых)</i>\n\n"
        f"🆕 Ждут подтверждения: <b>{new_count}</b>\n"
        f"🔄 В работе: <b>{in_work}</b>\n"
        f"⚠️ Товаров с низким остатком: <b>{low_stock}</b>"
    )
    show_screen(
        chat_id, telegram_user_id, text,
        inline(
            [button("🆕 Новые заказы", "a:orders:new:0"), button("⚠️ Остатки", "a:stock")],
            HOME_ROW,
        ),
        message_id,
    )


def admin_stock_screen(chat_id, telegram_user_id, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    with session() as db:
        products = (
            db.query(Product)
            .filter(Product.is_active == 1, Product.stock_quantity <= LOW_STOCK_LIMIT)
            .order_by(Product.stock_quantity)
            .limit(20)
            .all()
        )
        lines = [f"⚠️ <b>Остаток {LOW_STOCK_LIMIT} и меньше</b>", ""]
        if not products:
            lines.append("Всё в порядке — низких остатков нет.")
        for product in products:
            lines.append(
                f"• {html.escape(product.name)} — "
                f"<b>{format_quantity(product.stock_quantity)} {html.escape(product.unit)}</b>"
            )
    rows = []
    if store_info.YANDEX_MAPS_URL:
        rows.append([{"text": "🗺 Открыть в Яндекс Картах", "url": store_info.YANDEX_MAPS_URL}])
    show_screen(chat_id, telegram_user_id, "\n".join(lines), inline(*rows, HOME_ROW), message_id)


# ---------------------------------------------------------------- Владелец


def require_owner(chat_id, telegram_user_id, message_id=None):
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is not None and user.role == "ADMIN" and user.is_owner == 1:
            return user.id
    show_screen(
        chat_id, telegram_user_id,
        "⛔ Управлять администраторами может только владелец магазина.",
        inline(HOME_ROW), message_id,
    )
    return None


def admins_screen(chat_id, telegram_user_id, message_id=None, notice=""):
    if require_owner(chat_id, telegram_user_id, message_id) is None:
        return
    with session() as db:
        admins = list_admins(db)
        lines = ["👥 <b>Администраторы</b>", ""]
        rows = []
        for admin in admins:
            name = html.escape(admin.phone or admin.email or f"№{admin.id}")
            telegram_mark = "📲" if has_telegram(db, admin) else "—"
            owner_mark = " 👑 владелец" if admin.is_owner == 1 else ""
            lines.append(f"{telegram_mark} {name}{owner_mark}")
            if admin.is_owner != 1:
                rows.append([button(f"➖ Снять {admin.phone or admin.email}", f"adm:del:{admin.id}")])
    lines += ["", "📲 — вошёл в этого бота и получает уведомления."]
    if notice:
        lines += ["", notice]
    show_screen(
        chat_id, telegram_user_id, "\n".join(lines),
        inline([button("➕ Добавить администратора", "adm:add")], *rows, HOME_ROW),
        message_id,
    )


def admin_add_prompt(chat_id, telegram_user_id, message_id=None):
    if require_owner(chat_id, telegram_user_id, message_id) is None:
        return
    user_states[telegram_user_id] = {"step": "add_admin"}
    show_screen(
        chat_id, telegram_user_id,
        "➕ <b>Новый администратор</b>\n\n"
        "Отправь телефон или email человека. Он должен быть уже "
        "зарегистрирован на сайте.",
        inline([button("✖️ Отмена", "adm:list")]),
        message_id,
    )


def handle_add_admin_message(message: dict) -> None:
    chat_id = message["chat"]["id"]
    telegram_user_id = message["from"]["id"]
    login = (message.get("text") or "").strip()
    delete_message(chat_id, message["message_id"])
    user_states.pop(telegram_user_id, None)
    if require_owner(chat_id, telegram_user_id) is None:
        return
    with session() as db:
        try:
            user = add_admin(db, login)
            notice = f"✅ {html.escape(user.phone or user.email)} теперь администратор."
        except AdminServiceError as error:
            notice = f"⚠️ {html.escape(str(error))}"
    admins_screen(chat_id, telegram_user_id, notice=notice)


def admin_remove(chat_id, telegram_user_id, admin_id, message_id=None):
    owner_id = require_owner(chat_id, telegram_user_id, message_id)
    if owner_id is None:
        return
    with session() as db:
        actor = db.get(User, owner_id)
        try:
            user = remove_admin(db, admin_id, actor)
            notice = f"✅ {html.escape(user.phone or user.email)} больше не администратор."
        except AdminServiceError as error:
            notice = f"⚠️ {html.escape(str(error))}"
    admins_screen(chat_id, telegram_user_id, message_id, notice)


# ---------------------------------------------------------------- Обработчики


MENU_ACTIONS = {
    "🔑 Войти": login_prompt,
    "🛍 Каталог": catalog_screen,
    "👤 Профиль": profile_screen,
    "📦 Мои заказы": customer_orders_screen,
    "🔔 Уведомления": customer_notifications_screen,
    "📋 Заказы": admin_orders_screen,
    "📊 Сводка": admin_summary_screen,
    "⚠️ Остатки": admin_stock_screen,
    "👥 Администраторы": admins_screen,
    "📞 Контакты": contacts_screen,
}

SLASH_COMMANDS = {
    "/catalog": catalog_screen,
    "/orders": lambda chat_id, user_id: orders_command(chat_id, user_id),
    "/contacts": contacts_screen,
    "/help": help_screen,
}


def orders_command(chat_id: int, telegram_user_id: int):
    """/orders: покупателю — его заказы, админу — новые заказы."""
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        role = user.role if user else None
    if role == "ADMIN":
        admin_orders_screen(chat_id, telegram_user_id)
    else:
        customer_orders_screen(chat_id, telegram_user_id)


def handle_message(message: dict) -> None:
    chat = message.get("chat", {})
    sender = message.get("from", {})
    chat_id = chat.get("id")
    telegram_user_id = sender.get("id")
    text = (message.get("text") or "").strip()
    if not chat_id or not telegram_user_id or chat.get("type") != "private":
        return

    if text in ("/cancel", "/start"):
        user_states.pop(telegram_user_id, None)
        home_screen(chat_id, telegram_user_id)
        return

    state = user_states.get(telegram_user_id)
    if state and state["step"] in ("login", "password"):
        handle_login_message(message, state)
        return
    if state and state["step"] == "add_admin":
        handle_add_admin_message(message)
        return

    action = MENU_ACTIONS.get(text) or SLASH_COMMANDS.get(text.split("@")[0])
    if action is not None:
        delete_message(chat_id, message["message_id"])
        action(chat_id, telegram_user_id)
        return

    # Посторонний текст удаляем, чтобы чат не засорялся
    delete_message(chat_id, message["message_id"])


def parse_int(value: str, default: int = 0) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def handle_callback(callback: dict) -> None:
    callback_id = callback["id"]
    data = callback.get("data", "")
    message = callback.get("message") or {}
    chat = message.get("chat") or {}
    if chat.get("type") != "private":
        answer_callback(callback_id, "Открой личный чат с ботом.", alert=True)
        return
    telegram_user_id = callback["from"]["id"]
    chat_id = chat["id"]
    message_id = message.get("message_id")
    parts = data.split(":")
    reply = ""

    if data == "home":
        user_states.pop(telegram_user_id, None)
        home_screen(chat_id, telegram_user_id)
    elif data == "login":
        login_prompt(chat_id, telegram_user_id)
    elif data == "logout":
        logout(chat_id, telegram_user_id)
    elif data == "catalog":
        catalog_screen(chat_id, telegram_user_id, message_id)
    elif parts[0] == "cat" and len(parts) == 3:
        category_screen(chat_id, telegram_user_id, parse_int(parts[1]), parse_int(parts[2]), message_id)
    elif parts[0] == "c" and len(parts) >= 3:
        action, value = parts[1], parse_int(parts[2])
        if action == "orders":
            customer_orders_screen(chat_id, telegram_user_id, value, message_id)
        elif action == "order":
            back = parse_int(parts[3]) if len(parts) > 3 else 0
            customer_order_screen(chat_id, telegram_user_id, value, back, message_id)
        elif action == "cancel":
            customer_cancel_confirm(chat_id, telegram_user_id, value, message_id)
        elif action == "cancelok":
            reply = customer_cancel(chat_id, telegram_user_id, value, message_id)
    elif data == "n:readall":
        mark_notifications_read(chat_id, telegram_user_id, message_id)
    elif parts[0] == "a" and len(parts) >= 2:
        if parts[1] == "orders" and len(parts) == 4:
            admin_orders_screen(chat_id, telegram_user_id, parts[2], parse_int(parts[3]), message_id)
        elif parts[1] == "order" and len(parts) == 4:
            admin_order_screen(chat_id, telegram_user_id, parse_int(parts[2]), parts[3], message_id)
        elif parts[1] == "stock":
            admin_stock_screen(chat_id, telegram_user_id, message_id)
    elif parts[0] == "order" and len(parts) == 3:
        # Кнопки статуса: из уведомления меняем статус прямо в этом сообщении
        reply = admin_change_status(chat_id, telegram_user_id, parse_int(parts[1]), parts[2], message_id)
    elif parts[0] == "adm":
        if parts[1] == "list":
            user_states.pop(telegram_user_id, None)
            admins_screen(chat_id, telegram_user_id, message_id)
        elif parts[1] == "add":
            admin_add_prompt(chat_id, telegram_user_id, message_id)
        elif parts[1] == "del" and len(parts) == 3:
            show_screen(
                chat_id, telegram_user_id,
                "Снять права администратора?",
                inline(
                    [button("Да, снять", f"adm:delok:{parts[2]}")],
                    [button("Отмена", "adm:list")],
                ),
                message_id,
            )
        elif parts[1] == "delok" and len(parts) == 3:
            admin_remove(chat_id, telegram_user_id, parse_int(parts[2]), message_id)
    else:
        reply = "Кнопка устарела — открой раздел заново."

    answer_callback(callback_id, reply)


def main() -> None:
    if not TOKEN:
        raise RuntimeError("Укажи TELEGRAM_BOT_TOKEN в backend/.env")

    # Бот работает через long polling; webhook от другого запуска мешает getUpdates
    # Сеть до Telegram бывает нестабильной: при старте не падаем, а ждём и пробуем снова
    delay = 3
    while True:
        try:
            telegram_request("deleteWebhook", {"drop_pending_updates": False})
            break
        except KeyboardInterrupt:
            return
        except Exception as error:
            logger.warning("Telegram недоступен при запуске (%s), повтор через %s с", error, delay)
            time.sleep(delay)
            delay = min(delay * 2, 60)
    setup_bot_profile()
    logger.info("Telegram-бот запускается; polling включён.")
    offset = None
    while True:
        try:
            payload = {"timeout": 25, "allowed_updates": ["message", "callback_query"]}
            if offset is not None:
                payload["offset"] = offset
            updates = telegram_request("getUpdates", payload)
            for update in updates:
                offset = update["update_id"] + 1
                try:
                    if update.get("message"):
                        handle_message(update["message"])
                    elif update.get("callback_query"):
                        handle_callback(update["callback_query"])
                except Exception:
                    logger.exception("Ошибка обработки update_id=%s", update.get("update_id"))
        except KeyboardInterrupt:
            logger.info("Telegram-бот остановлен.")
            break
        except Exception:
            logger.exception("Ошибка опроса Telegram API")
            time.sleep(3)


if __name__ == "__main__":
    main()
