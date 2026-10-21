"""Сессия базы, вход через привязку Telegram и проверка роли."""

from contextlib import contextmanager
from datetime import UTC, datetime, timedelta, timezone

from app.database import SessionLocal
from app.models import (
    TelegramAccountLink,
    User,
)

from .telegram import HOME_ROW, inline, show_screen


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
        value = value.replace(tzinfo=UTC)
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
