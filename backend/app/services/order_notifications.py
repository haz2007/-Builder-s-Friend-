"""Тексты и рассылка уведомлений о заказах в Telegram.

Кто получает уведомления:
- покупатель — только о своих заказах и только пока его аккаунт сайта
  привязан к боту (после «Выйти» в боте сообщения не приходят);
- администраторы — обо всех заказах, если вошли в бот, с кнопками смены
  статуса. Админ, который сам поменял статус, второе сообщение не получает.

На сайте покупатель видит уведомления в колокольчике (таблица notifications).
"""

import html
import logging

from sqlalchemy.orm import Session, joinedload

from .. import store_info
from ..database import SessionLocal
from ..models import Order, OrderItem, TelegramAccountLink, User
from .order_service import ALLOWED_TRANSITIONS, get_status_value
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

ACTION_LABELS = {
    "CONFIRMED": "✅ Подтвердить заказ",
    "PREPARING": "🪚 Начать подготовку",
    "READY_FOR_DELIVERY": "📦 Отметить готовым к выдаче",
    "ASSIGNED_TO_DRIVER": "🚚 Назначить водителя",
    "ON_THE_WAY": "🛻 Заказ в пути",
    "DELIVERED": "🎉 Отметить доставленным",
    "CANCELLED": "❌ Отменить заказ",
}

STATUS_ORDER = [
    "CONFIRMED",
    "PREPARING",
    "READY_FOR_DELIVERY",
    "ASSIGNED_TO_DRIVER",
    "ON_THE_WAY",
    "DELIVERED",
    "CANCELLED",
]


def status_name(status) -> str:
    value = get_status_value(status)
    return STATUS_NAMES.get(value, value)


def format_money(value: float) -> str:
    return f"{value:,.0f}".replace(",", " ") + " ₽"


def format_quantity(value: float) -> str:
    return f"{value:g}"


def build_order_keyboard(order_id: int, status) -> dict | None:
    """Кнопки только для допустимых следующих статусов."""
    next_statuses = ALLOWED_TRANSITIONS.get(get_status_value(status), set())

    rows = [
        [{
            "text": ACTION_LABELS[next_status],
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
        f"📌 Статус: <b>{status_name(order.status)}</b>",
    ]

    return "\n".join(lines)


def build_customer_message(order: Order, title: str) -> str:
    """Сообщение покупателю: без служебных данных."""
    lines = [
        f"<b>{html.escape(title)}</b>",
        "",
        *order_item_lines(order),
        "",
        f"💰 Сумма: <b>{format_money(order.total_price)}</b>",
        delivery_line(order),
        f"📌 Статус: <b>{status_name(order.status)}</b>",
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


def notify_order_event(
    order_id: int,
    admin_title: str,
    customer_title: str | None,
    actor_user_id: int | None = None,
) -> None:
    """Рассылает уведомление о заказе. Ошибки Telegram заказ не ломают.

    Открывает свою сессию БД, поэтому подходит для BackgroundTasks и бота.
    """
    db = SessionLocal()
    try:
        order = load_order(db, order_id)
        if order is None:
            return

        if customer_title:
            link = customer_link(db, order)
            # Если покупатель сам админ, он и так получит сообщение как админ
            if link is not None and order.user.role != "ADMIN":
                send_telegram_message(
                    link.telegram_chat_id,
                    build_customer_message(order, customer_title),
                )

        admin_text = build_order_message(order, admin_title)
        keyboard = build_order_keyboard(order.id, order.status)

        for link in admin_links(db):
            if link.user_id == actor_user_id:
                continue
            send_telegram_message(link.telegram_chat_id, admin_text, keyboard)
    except Exception:
        logger.exception("Не удалось разослать уведомления о заказе №%s", order_id)
    finally:
        db.close()


def notify_order_created(order_id: int) -> None:
    notify_order_event(
        order_id,
        admin_title=f"🛒 Новый заказ №{order_id}",
        customer_title=f"✅ Заказ №{order_id} оформлен",
    )


def notify_order_status_changed(
    order_id: int,
    previous_status: str,
    new_status: str,
    actor_user_id: int | None,
) -> None:
    notify_order_event(
        order_id,
        admin_title=(
            f"🔔 Заказ №{order_id}: {status_name(previous_status)} → "
            f"{status_name(new_status)}"
        ),
        customer_title=f"🔔 Заказ №{order_id}: {status_name(new_status)}",
        actor_user_id=actor_user_id,
    )

    if get_status_value(new_status) == "DELIVERED":
        send_review_request(order_id)


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


def send_review_request(order_id: int) -> None:
    """Просьба об отзыве — только покупателю, вошедшему в бота."""
    keyboard = review_keyboard()
    if keyboard is None:
        return

    db = SessionLocal()
    try:
        order = load_order(db, order_id)
        if order is None or order.user.role == "ADMIN":
            return
        link = customer_link(db, order)
        if link is not None:
            send_telegram_message(link.telegram_chat_id, build_review_request(order), keyboard)
    except Exception:
        logger.exception("Не удалось отправить просьбу об отзыве по заказу №%s", order_id)
    finally:
        db.close()


def notify_order_cancelled_by_customer(order_id: int) -> None:
    notify_order_event(
        order_id,
        admin_title=f"❌ Заказ №{order_id} отменён покупателем",
        customer_title=f"Заказ №{order_id} отменён",
    )
