"""Тексты уведомлений о заказах и их надёжная доставка в Telegram.

Кто получает уведомления:
- покупатель — только о своих заказах и только пока его аккаунт сайта
  привязан к боту (после «Выйти» в боте сообщения не приходят);
- администраторы — обо всех заказах, если вошли в бот, с кнопками смены
  статуса. Админ, который сам поменял статус, второе сообщение не получает.

Доставка — через transactional outbox: сообщения записываются в таблицу
telegram_outbox в той же транзакции, что и заказ (queue_*), а отправляет
их deliver_pending() — API сразу после ответа, бот — раз в несколько секунд.

На сайте покупатель видит уведомления в колокольчике (таблица notifications).
"""

import html
import logging
from datetime import UTC, datetime, timedelta

from sqlalchemy.orm import Session, joinedload

from .. import store_info
from ..database import SessionLocal
from ..models import Order, OrderItem, OutboxMessage, TelegramAccountLink, User
from .order_service import allowed_transitions, get_status_value
from .telegram_service import send_telegram_message

logger = logging.getLogger(__name__)


STATUS_NAMES = {
    "NEW": "Новый заказ",
    "CONFIRMED": "Подтверждён",
    "PREPARING": "Готовится",
    "READY_FOR_DELIVERY": "Готов к доставке",
    "ASSIGNED_TO_DRIVER": "Водитель назначен",
    "ON_THE_WAY": "В пути",
    "DELIVERED": "Доставлен",
    "CANCELLED": "Отменён",
}

# Самовывоз: заказ не везут, а выдают на складе
PICKUP_STATUS_NAMES = {
    **STATUS_NAMES,
    "READY_FOR_DELIVERY": "Готов к выдаче",
    "DELIVERED": "Выдан",
}

ACTION_LABELS = {
    "CONFIRMED": "✅ Подтвердить заказ",
    "PREPARING": "🪚 Начать подготовку",
    "READY_FOR_DELIVERY": "📦 Заказ собран",
    "ON_THE_WAY": "🛻 Заказ в пути",
    "DELIVERED": "🎉 Отметить доставленным",
    "CANCELLED": "❌ Отменить заказ",
}

PICKUP_ACTION_LABELS = {
    **ACTION_LABELS,
    "READY_FOR_DELIVERY": "📦 Собран — ждёт покупателя",
    "DELIVERED": "🤝 Выдан покупателю",
}

STATUS_ORDER = [
    "CONFIRMED",
    "PREPARING",
    "READY_FOR_DELIVERY",
    "ON_THE_WAY",
    "DELIVERED",
    "CANCELLED",
]


def status_name(status, delivery_method: str | None = None) -> str:
    value = get_status_value(status)
    names = PICKUP_STATUS_NAMES if delivery_method == "PICKUP" else STATUS_NAMES
    return names.get(value, value)


def format_money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ") + " ₽"


def format_quantity(value: float) -> str:
    return f"{value:g}"


def build_order_keyboard(
    order_id: int, status, delivery_method: str | None = None
) -> dict | None:
    """Кнопки только для допустимых следующих статусов."""
    next_statuses = allowed_transitions(status, delivery_method)
    labels = PICKUP_ACTION_LABELS if delivery_method == "PICKUP" else ACTION_LABELS

    rows = [
        [{
            "text": labels[next_status],
            "callback_data": f"order:{order_id}:{next_status}",
        }]
        for next_status in STATUS_ORDER
        if next_status in next_statuses
    ]

    return {"inline_keyboard": rows} if rows else None


def order_item_lines(order: Order) -> list[str]:
    lines = []

    for item in order.items:
        name = html.escape(
            getattr(item.product, "name", None) or f"Товар №{item.product_id}"
        )
        variant_name = getattr(item.variant, "name", None)
        if variant_name and variant_name != item.unit:
            name = f"{name} ({html.escape(variant_name)})"

        lines.append(
            f"• {name} — {format_quantity(item.quantity)} {html.escape(item.unit)}"
            f" × {format_money(item.price)} = "
            f"{format_money(item.price * item.quantity)}"
        )

    return lines


def delivery_line(order: Order) -> str:
    if order.delivery_method == "PICKUP":
        return "🏬 Самовывоз со склада"
    return f"🚚 Доставка: {html.escape(order.delivery_address or 'адрес не указан')}"


def build_order_message(order: Order, title: str) -> str:
    """Подробное сообщение для администратора (с контактами покупателя)."""
    customer_phone = order.customer_phone or "не указан"

    lines = [
        f"<b>{html.escape(title)}</b>",
        "",
        f"👤 Покупатель: {html.escape(order.customer_name or 'Имя не указано')}",
        f"📞 Телефон: {html.escape(customer_phone)}",
        "",
        "🧾 Товары:",
        *order_item_lines(order),
        "",
        f"💰 Итого: <b>{format_money(order.total_price)}</b>",
        delivery_line(order),
        *comment_lines(order),
        f"📌 Статус: <b>{status_name(order.status, order.delivery_method)}</b>",
    ]

    return "\n".join(lines)


def comment_lines(order: Order) -> list[str]:
    return [f"💬 Комментарий: <i>{html.escape(order.comment)}</i>"] if order.comment else []


def build_customer_message(order: Order, title: str) -> str:
    """Сообщение покупателю: без служебных данных."""
    lines = [
        f"<b>{html.escape(title)}</b>",
        "",
        *order_item_lines(order),
        "",
        f"💰 Сумма: <b>{format_money(order.total_price)}</b>",
        delivery_line(order),
        f"📌 Статус: <b>{status_name(order.status, order.delivery_method)}</b>",
    ]

    return "\n".join(lines)


def load_order(db: Session, order_id: int) -> Order | None:
    return (
        db.query(Order)
        .options(
            joinedload(Order.items).joinedload(OrderItem.product),
            joinedload(Order.items).joinedload(OrderItem.variant),
            joinedload(Order.user),
        )
        .filter(Order.id == order_id)
        .first()
    )


def admin_links(db: Session) -> list[TelegramAccountLink]:
    return (
        db.query(TelegramAccountLink)
        .join(User, User.id == TelegramAccountLink.user_id)
        .filter(User.role == "ADMIN")
        .all()
    )


def customer_link(db: Session, order: Order) -> TelegramAccountLink | None:
    return (
        db.query(TelegramAccountLink)
        .filter(TelegramAccountLink.user_id == order.user_id)
        .first()
    )


Message = tuple[int, str, dict | None]


def order_event_messages(
    db: Session,
    order: Order,
    admin_title: str,
    customer_title: str | None,
    actor_user_id: int | None = None,
) -> list[Message]:
    """Кому и что отправить о событии заказа: покупателю (если вошёл в бота)
    и всем админам в боте, кроме того, кто сам совершил действие."""
    messages: list[Message] = []

    if customer_title:
        link = customer_link(db, order)
        # Если покупатель сам админ, он и так получит сообщение как админ
        if link is not None and order.user.role != "ADMIN":
            messages.append((link.telegram_chat_id, build_customer_message(order, customer_title), None))

    admin_text = build_order_message(order, admin_title)
    keyboard = build_order_keyboard(order.id, order.status, order.delivery_method)
    for link in admin_links(db):
        if link.user_id != actor_user_id:
            messages.append((link.telegram_chat_id, admin_text, keyboard))
    return messages


def enqueue(db: Session, messages: list[Message]) -> None:
    """Кладёт сообщения в outbox — в текущей транзакции, без commit."""
    for chat_id, text, markup in messages:
        db.add(OutboxMessage(chat_id=chat_id, text=text, reply_markup=markup))


def queue_order_created(db: Session, order: Order) -> None:
    enqueue(db, order_event_messages(
        db, order,
        admin_title=f"🛒 Новый заказ №{order.id}",
        customer_title=f"✅ Заказ №{order.id} оформлен",
    ))


def queue_status_changed(
    db: Session,
    order: Order,
    previous_status: str,
    new_status: str,
    actor_user_id: int | None,
) -> None:
    method = order.delivery_method
    enqueue(db, order_event_messages(
        db, order,
        admin_title=(
            f"🔔 Заказ №{order.id}: {status_name(previous_status, method)} → {status_name(new_status, method)}"
        ),
        customer_title=f"🔔 Заказ №{order.id}: {status_name(new_status, method)}",
        actor_user_id=actor_user_id,
    ))
    if get_status_value(new_status) == "DELIVERED":
        enqueue(db, review_request_messages(db, order))


def queue_cancelled_by_customer(db: Session, order: Order) -> None:
    enqueue(db, order_event_messages(
        db, order,
        admin_title=f"❌ Заказ №{order.id} отменён покупателем",
        customer_title=f"Заказ №{order.id} отменён",
    ))


MAX_ATTEMPTS = 8


def _utcnow() -> datetime:
    return datetime.now(UTC).replace(tzinfo=None)


def deliver_pending(limit: int = 50) -> int:
    """Отправляет ждущие сообщения из outbox; возвращает, сколько ушло.

    FOR UPDATE SKIP LOCKED: API и бот могут вызывать это одновременно —
    каждое сообщение возьмёт только один из них, дублей не будет.
    """
    db = SessionLocal()
    sent = 0
    try:
        now = _utcnow()
        batch = (
            db.query(OutboxMessage)
            .filter(OutboxMessage.status == "pending", OutboxMessage.next_attempt_at <= now)
            .order_by(OutboxMessage.id)
            .limit(limit)
            .with_for_update(skip_locked=True)
            .all()
        )
        for message in batch:
            error = ""
            try:
                ok = send_telegram_message(message.chat_id, message.text, message.reply_markup)
            except Exception as exc:  # сеть, Telegram — пробуем позже
                ok, error = False, str(exc)
            if ok:
                message.status, message.sent_at = "sent", now
                sent += 1
                continue
            message.attempts += 1
            message.last_error = (error or "Telegram не принял сообщение")[:500]
            if message.attempts >= MAX_ATTEMPTS:
                message.status = "failed"
            else:
                # 10 с, 20 с, 40 с … но не реже чем раз в 10 минут
                message.next_attempt_at = now + timedelta(seconds=min(5 * 2 ** message.attempts, 600))
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Не удалось обработать очередь сообщений Telegram")
    finally:
        db.close()
    return sent


def review_keyboard() -> dict | None:
    if not store_info.YANDEX_REVIEW_URL:
        return None
    return {"inline_keyboard": [[
        {"text": "⭐ Оставить отзыв на Яндекс Картах", "url": store_info.YANDEX_REVIEW_URL},
    ]]}


def build_review_request(order: Order) -> str:
    received = "выдан" if order.delivery_method == "PICKUP" else "доставлен"
    return (
        f"🙏 <b>Спасибо, что выбрали «{html.escape(store_info.STORE_NAME)}»!</b>\n\n"
        f"Заказ №{order.id} {received}. Если всё понравилось — оставьте, "
        "пожалуйста, отзыв на Яндекс Картах. Для семейного магазина это "
        "очень важно, а другим строителям поможет нас найти.\n\n"
        "Если что-то пошло не так — напишите или позвоните нам, разберёмся."
    )


def review_request_messages(db: Session, order: Order) -> list[Message]:
    """Просьба об отзыве — только покупателю, вошедшему в бота."""
    keyboard = review_keyboard()
    if keyboard is None or order.user.role == "ADMIN":
        return []
    link = customer_link(db, order)
    return [(link.telegram_chat_id, build_review_request(order), keyboard)] if link else []
