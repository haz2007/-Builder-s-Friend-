"""Сроки хранения персональных данных (ч. 4 ст. 21 152-ФЗ: цель обработки
достигнута — данные уничтожаются не позже чем через 30 дней).

- копии сообщений Telegram из очереди (в них имя, телефон, адрес) — 7 дней;
- заявки на звонок, по которым уже перезвонили, — 30 дней после звонка;
- в выданных и отменённых заказах покупателя, удалившего аккаунт, стираются
  имя, адрес и комментарий; состав, сумма и дата остаются для учёта.

Проход, который что-то удалил, оставляет запись в журнале действий: выгрузка
журнала подтверждает уничтожение данных (приказ Роскомнадзора № 179).
Запускается раз в сутки: scripts/purge-expired.sh → manage.py purge-expired.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import or_
from sqlalchemy.orm import Session

from ..models import CallbackRequest, Order, OutboxMessage, User
from . import audit

OUTBOX_KEEP_DAYS = 7
CALLBACK_KEEP_DAYS = 30
# Заказ выдан или отменён — контакты покупателя для него больше не нужны
FINISHED_ORDER_STATUSES = ("DELIVERED", "CANCELLED")
DELETED_CUSTOMER_NAME = "Аккаунт удалён"


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def wipe_finished_order_contacts(db: Session, user_ids: list[int]) -> int:
    """Стирает контакты в завершённых заказах этих покупателей. Без commit."""
    if not user_ids:
        return 0
    orders = (
        db.query(Order)
        .filter(
            Order.user_id.in_(user_ids),
            Order.status.in_(FINISHED_ORDER_STATUSES),
            or_(
                Order.customer_name != DELETED_CUSTOMER_NAME,
                Order.delivery_address != "",
                Order.comment.isnot(None),
            ),
        )
        .all()
    )
    for order in orders:
        order.customer_name = DELETED_CUSTOMER_NAME
        order.delivery_address = ""
        order.comment = None
    return len(orders)


def deleted_customer_ids(db: Session) -> list[int]:
    """Обезличенные аккаунты: после удаления у покупателя нет ни телефона, ни почты."""
    rows = (
        db.query(User.id)
        .filter(User.role == "CUSTOMER", User.phone.is_(None), User.email.is_(None))
        .all()
    )
    return [row.id for row in rows]


def purge_expired(db: Session, now: datetime | None = None) -> dict[str, int]:
    """Удаляет всё, чей срок хранения вышел, и пишет об этом в журнал."""
    now = now or _utcnow()

    outbox = (
        db.query(OutboxMessage)
        .filter(
            OutboxMessage.status.in_(("sent", "failed")),
            OutboxMessage.created_at < now - timedelta(days=OUTBOX_KEEP_DAYS),
        )
        .delete(synchronize_session=False)
    )
    callbacks = (
        db.query(CallbackRequest)
        .filter(
            CallbackRequest.status == "DONE",
            CallbackRequest.handled_at < now - timedelta(days=CALLBACK_KEEP_DAYS),
        )
        .delete(synchronize_session=False)
    )
    # Заказы, которые завершились уже после удаления аккаунта
    orders = wipe_finished_order_contacts(db, deleted_customer_ids(db))

    counts = {"outbox": outbox, "callbacks": callbacks, "orders": orders}
    if any(counts.values()):
        audit.record(
            db, None, "data.purged", "retention", None,
            f"Удалено по сроку хранения: сообщений Telegram — {outbox}, "
            f"заявок на звонок — {callbacks}, заказов без контактов — {orders}",
        )
    db.commit()
    return counts
