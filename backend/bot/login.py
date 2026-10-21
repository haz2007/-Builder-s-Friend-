"""Вход в бота по телефону (или email админа) и паролю сайта."""



from app.auth import find_user_by_email, find_user_by_phone, verify_password
from app.models import (
    TelegramAccountLink,
)
from app.rate_limit import telegram_login_limiter, wait_text

from .config import logger, user_states
from .context import get_link, session
from .screens import home_screen
from .telegram import HOME_ROW, button, delete_message, inline, show_screen


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
