"""Общие экраны: главное меню, профиль, выход, контакты, помощь, профиль бота."""

import html

from app import store_info
from app.models import (
    Order,
)

from .config import ROLE_NAMES, logger, user_states
from .context import get_link, get_logged_user, main_keyboard, session
from .telegram import HOME_ROW, button, inline, show_screen, telegram_request


def home_screen(chat_id: int, telegram_user_id: int):
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is None:
            text = (
                "👋 <b>Добро пожаловать в «Друг Строителя»!</b>\n\n"
                f"Семейный магазин пиломатериалов — {store_info.YEARS_ON_MARKET} лет опыта. "
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
        f"✉️ {store_info.EMAIL}",
        f"🕘 {store_info.WORKING_HOURS}",
    ]
    if store_info.ADDRESS:
        lines.append(f"📍 {html.escape(store_info.ADDRESS)}")
    lines += [
        "",
        "🚚 Привезём на объект своим транспортом или отгрузим на вашу машину. "
        "Стоимость доставки обсудим по телефону.",
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
