"""Покупатель: свои заказы, отмена нового заказа, уведомления."""

import html

from fastapi import HTTPException

from app import store_info
from app.models import (
    Notification,
    Order,
    OrderStatusHistory,
)
from app.services.order_notifications import (
    build_customer_message,
    format_money,
    load_order,
    notify_order_cancelled_by_customer,
    status_name,
)
from app.services.order_service import (
    change_order_status,
    get_status_value,
)
from app.services.variant_service import restore_order_stock

from .config import PAGE_SIZE
from .context import format_date, require_user, session
from .telegram import HOME_ROW, button, inline, show_screen


def customer_orders_screen(chat_id, telegram_user_id, page=0, message_id=None):
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return
    with session() as db:
        query = db.query(Order).filter(Order.user_id == user_id)
        total = query.count()
        if total == 0:
            show_screen(
                chat_id, telegram_user_id,
                "📦 <b>Мои заказы</b>\n\nЗаказов пока нет — оформи первый на сайте.",
                inline(HOME_ROW), message_id,
            )
            return
        max_page = (total - 1) // PAGE_SIZE
        page = max(0, min(page, max_page))
        orders = query.order_by(Order.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE).all()
        rows = [
            [button(
                f"№{order.id} · {status_name(order.status, order.delivery_method)} · {format_money(order.total_price)}",
                f"c:order:{order.id}:{page}",
            )]
            for order in orders
        ]
    navigation = []
    if page > 0:
        navigation.append(button("◀️ Назад", f"c:orders:{page - 1}"))
    if page < max_page:
        navigation.append(button("Вперёд ▶️", f"c:orders:{page + 1}"))
    show_screen(
        chat_id, telegram_user_id,
        f"📦 <b>Мои заказы</b>\n\nВсего: {total} · страница {page + 1} из {max_page + 1}",
        inline(*rows, navigation, HOME_ROW),
        message_id,
    )


def status_history_lines(db, order: Order, show_actor: bool = False) -> list[str]:
    """История статусов; администратору — ещё и кто менял статус."""
    history = (
        db.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == order.id)
        .order_by(OrderStatusHistory.id)
        .all()
    )
    if not history:
        return []
    lines = []
    for entry in history:
        line = f"  {format_date(entry.created_at)} — {status_name(entry.status, order.delivery_method)}"
        if show_actor and entry.changed_by_label:
            line += f" · {html.escape(entry.changed_by_label)}"
        lines.append(line)
    return ["", "🕓 <b>История:</b>"] + lines


def customer_order_screen(chat_id, telegram_user_id, order_id, back_page=0, message_id=None):
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return
    with session() as db:
        order = load_order(db, order_id)
        if order is None or order.user_id != user_id:
            show_screen(chat_id, telegram_user_id, "Заказ не найден.", inline(HOME_ROW), message_id)
            return
        text = "\n".join(
            [build_customer_message(order, f"📦 Заказ №{order.id}")]
            + status_history_lines(db, order)
        )
        can_cancel = get_status_value(order.status) == "NEW"
        delivered = get_status_value(order.status) == "DELIVERED"
    rows = []
    if can_cancel:
        rows.append([button("❌ Отменить заказ", f"c:cancel:{order_id}")])
    if delivered and store_info.YANDEX_REVIEW_URL:
        rows.append([{"text": "⭐ Оставить отзыв на Яндекс Картах", "url": store_info.YANDEX_REVIEW_URL}])
    rows.append([button("◀️ К заказам", f"c:orders:{back_page}")])
    show_screen(chat_id, telegram_user_id, text, inline(*rows, HOME_ROW), message_id)


def customer_cancel_confirm(chat_id, telegram_user_id, order_id, message_id=None):
    show_screen(
        chat_id, telegram_user_id,
        f"Точно отменить заказ №{order_id}? Товар вернётся на склад.",
        inline(
            [button("Да, отменить", f"c:cancelok:{order_id}")],
            [button("Нет, оставить", f"c:order:{order_id}:0")],
        ),
        message_id,
    )


def customer_cancel(chat_id, telegram_user_id, order_id, message_id=None) -> str:
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return ""
    with session() as db:
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if order is None or order.user_id != user_id:
            return "Заказ не найден."
        if get_status_value(order.status) != "NEW":
            return "Отменить можно только новый заказ — позвони в магазин."
        try:
            change_order_status(order, "CANCELLED", db, user_id)
            restore_order_stock(db, order)
            db.commit()
        except HTTPException as error:
            db.rollback()
            return str(error.detail)
    notify_order_cancelled_by_customer(order_id)
    customer_order_screen(chat_id, telegram_user_id, order_id, 0, message_id)
    return f"Заказ №{order_id} отменён"


def customer_notifications_screen(chat_id, telegram_user_id, message_id=None):
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return
    with session() as db:
        notifications = (
            db.query(Notification)
            .filter(Notification.user_id == user_id)
            .order_by(Notification.id.desc())
            .limit(10)
            .all()
        )
        unread = db.query(Notification).filter(
            Notification.user_id == user_id, Notification.is_read == 0
        ).count()
        lines = ["🔔 <b>Уведомления</b>", ""]
        if not notifications:
            lines.append("Уведомлений пока нет.")
        for notification in notifications:
            marker = "🔵" if notification.is_read == 0 else "⚪️"
            lines.append(
                f"{marker} {format_date(notification.created_at)} · заказ №{notification.order_id}\n"
                f"    {html.escape(notification.message)}"
            )
    rows = []
    if unread:
        rows.append([button(f"✔️ Отметить прочитанными ({unread})", "n:readall")])
    show_screen(chat_id, telegram_user_id, "\n".join(lines), inline(*rows, HOME_ROW), message_id)


def mark_notifications_read(chat_id, telegram_user_id, message_id=None):
    user_id = require_user(chat_id, telegram_user_id, {"CUSTOMER"}, message_id)
    if user_id is None:
        return
    with session() as db:
        db.query(Notification).filter(
            Notification.user_id == user_id, Notification.is_read == 0
        ).update({"is_read": 1})
        db.commit()
    customer_notifications_screen(chat_id, telegram_user_id, message_id)
