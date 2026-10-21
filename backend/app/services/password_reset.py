"""Сброс пароля.

1. Покупатель, который вошёл в Telegram-бота, получает от бота 6-значный код
   и сам задаёт новый пароль на сайте.
2. Если бот не подключён — администратор выдаёт временный пароль по телефону
   (только покупателям: так один админ не может захватить аккаунт другого).
"""

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session

from ..auth import find_user_by_phone, hash_password, verify_password
from ..models import PasswordResetCode, TelegramAccountLink, User
from . import audit
from .telegram_service import send_telegram_message

CODE_TTL = timedelta(minutes=10)
MAX_ATTEMPTS = 5


class PasswordResetError(Exception):
    pass


def _now() -> datetime:
    # В базе время хранится в UTC без пометки часового пояса
    return datetime.now(UTC).replace(tzinfo=None)


def request_code(db: Session, phone: str) -> tuple[int, str] | None:
    """Создаёт код и возвращает (chat_id, текст) для Telegram.

    None — номер не найден или аккаунт не привязан к боту. Ответ сайта
    в обоих случаях одинаковый, чтобы по нему нельзя было проверять,
    зарегистрирован ли номер.
    """
    user = find_user_by_phone(db, phone)
    if user is None:
        return None
    link = db.query(TelegramAccountLink).filter(TelegramAccountLink.user_id == user.id).first()
    if link is None:
        return None

    code = f"{secrets.randbelow(1_000_000):06d}"
    db.query(PasswordResetCode).filter(PasswordResetCode.user_id == user.id).delete()
    db.add(PasswordResetCode(user_id=user.id, code_hash=hash_password(code), expires_at=_now() + CODE_TTL))
    db.commit()

    text = (
        f"🔐 <b>Код для смены пароля: {code}</b>\n\n"
        "Введите его на сайте в течение 10 минут. Никому не сообщайте код — "
        "сотрудники магазина его никогда не спрашивают.\n\n"
        "Если вы не запрашивали смену пароля, просто проигнорируйте это сообщение."
    )
    return link.telegram_chat_id, text


def confirm_code(db: Session, phone: str, code: str, new_password: str) -> User:
    user = find_user_by_phone(db, phone)
    record = (
        db.query(PasswordResetCode).filter(PasswordResetCode.user_id == user.id).first() if user else None
    )
    if user is None or record is None or record.expires_at < _now():
        raise PasswordResetError("Код неверный или устарел. Запросите новый.")

    if not verify_password(code.strip(), record.code_hash):
        record.attempts += 1
        if record.attempts >= MAX_ATTEMPTS:
            db.delete(record)
        db.commit()
        raise PasswordResetError("Код неверный или устарел. Запросите новый.")

    user.password_hash = hash_password(new_password)
    db.delete(record)
    db.commit()
    return user


def send_code(chat_id: int, text: str) -> None:
    send_telegram_message(chat_id, text)


def temporary_password() -> str:
    """Восемь цифр — легко продиктовать по телефону, проходит проверку длины."""
    return f"{secrets.randbelow(100_000_000):08d}"


def reset_by_admin(db: Session, user_id: int, actor: User | None = None) -> tuple[User, str]:
    user = db.get(User, user_id)
    if user is None:
        raise PasswordResetError("Пользователь не найден.")
    if user.role != "CUSTOMER":
        raise PasswordResetError("Сбросить можно только пароль покупателя.")
    password = temporary_password()
    user.password_hash = hash_password(password)
    db.query(PasswordResetCode).filter(PasswordResetCode.user_id == user.id).delete()
    # Сам временный пароль в журнал не пишем
    audit.record(db, actor, "password.reset", "user", user.id,
                 f"Временный пароль покупателю {user.phone or f'№{user.id}'}")
    db.commit()
    return user, password
