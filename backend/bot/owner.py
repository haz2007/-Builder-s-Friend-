"""Владелец: назначает и снимает администраторов."""

import html

from app.models import (
    User,
)
from app.services.admin_service import (
    AdminServiceError,
    add_admin,
    has_telegram,
    list_admins,
    remove_admin,
)

from .config import user_states
from .context import get_logged_user, session
from .telegram import HOME_ROW, button, delete_message, inline, show_screen


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
    owner_id = require_owner(chat_id, telegram_user_id)
    if owner_id is None:
        return
    with session() as db:
        try:
            user = add_admin(db, login, db.get(User, owner_id))
            notice = f"✅ {html.escape(user.phone or user.email or f"№{user.id}")} теперь администратор."
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
            notice = f"✅ {html.escape(user.phone or user.email or f"№{user.id}")} больше не администратор."
        except AdminServiceError as error:
            notice = f"⚠️ {html.escape(str(error))}"
    admins_screen(chat_id, telegram_user_id, message_id, notice)
