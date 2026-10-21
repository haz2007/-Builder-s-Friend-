"""Разбор сообщений и нажатий кнопок: куда направить пользователя."""

from collections.abc import Callable

from .admin import (
    admin_change_status,
    admin_order_screen,
    admin_orders_screen,
    admin_stock_screen,
    admin_summary_screen,
)
from .catalog import catalog_screen, category_screen
from .config import user_states
from .context import get_logged_user, session
from .customer import (
    customer_cancel,
    customer_cancel_confirm,
    customer_notifications_screen,
    customer_order_screen,
    customer_orders_screen,
    mark_notifications_read,
)
from .login import handle_login_message, login_prompt
from .owner import (
    admin_add_prompt,
    admin_remove,
    admins_screen,
    handle_add_admin_message,
)
from .screens import contacts_screen, help_screen, home_screen, logout, profile_screen
from .telegram import answer_callback, button, delete_message, inline, show_screen

# Кнопки меню и команды: функция экрана (chat_id, telegram_user_id) → None
ScreenAction = Callable[[int, int], None]

MENU_ACTIONS: dict[str, ScreenAction] = {
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

SLASH_COMMANDS: dict[str, ScreenAction] = {
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
