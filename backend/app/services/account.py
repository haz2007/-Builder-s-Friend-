"""Удаление аккаунта покупателем — отзыв согласия на обработку данных (152-ФЗ).

Телефон, привязка Telegram, уведомления и коды сброса удаляются сразу.
Если заказы были, их записи остаются для учёта (закон об учёте требует
хранить сведения о продажах), но войти в аккаунт и узнать по нему
телефон больше нельзя: сам аккаунт обезличивается. В выданных и отменённых
заказах сразу стираются имя, адрес и комментарий; в незавершённых — когда
они завершатся (ежедневная очистка, services/retention.py).
"""

import secrets

from sqlalchemy.orm import Session

from ..auth import hash_password
from ..models import Notification, Order, PasswordResetCode, TelegramAccountLink, User
from . import audit
from .retention import wipe_finished_order_contacts


def delete_customer(db: Session, user: User) -> bool:
    """True — аккаунт удалён полностью, False — обезличен (есть заказы)."""
    db.query(TelegramAccountLink).filter(TelegramAccountLink.user_id == user.id).delete()
    db.query(PasswordResetCode).filter(PasswordResetCode.user_id == user.id).delete()
    db.query(Notification).filter(Notification.user_id == user.id).delete()

    has_orders = db.query(Order.id).filter(Order.user_id == user.id).first() is not None
    audit.record(db, None, "user.deleted", "user", user.id,
                 "Покупатель удалил аккаунт" + (" (заказы сохранены для учёта)" if has_orders else ""))
    if has_orders:
        user.phone = None
        user.email = None
        user.privacy_accepted_at = None
        # Случайный пароль, которого никто не знает: вход закрыт навсегда
        user.password_hash = hash_password(secrets.token_urlsafe(32))
        wipe_finished_order_contacts(db, [user.id])
    else:
        db.delete(user)
    db.commit()
    return not has_orders
