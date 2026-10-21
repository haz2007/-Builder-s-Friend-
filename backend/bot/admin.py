"""Администратор: заказы с фильтрами и сменой статуса, сводка, остатки."""

import html
from datetime import UTC, datetime, timedelta, timezone

from fastapi import HTTPException
from sqlalchemy import func

from app.models import (
    Order,
    OrderStatusHistory,
    Product,
)
from app.services import callbacks
from app.services.order_notifications import (
    build_order_keyboard,
    build_order_message,
    deliver_pending,
    format_money,
    load_order,
    queue_status_changed,
    status_name,
)
from app.services.order_service import (
    allowed_transitions,
    change_order_status,
    get_status_value,
)
from app.services.variant_service import restore_order_stock

from .config import LOW_STOCK_LIMIT, ORDER_FILTERS, PAGE_SIZE, logger
from .context import get_logged_user, require_user, session
from .customer import status_history_lines
from .telegram import HOME_ROW, button, edit_message, inline, show_screen


def admin_orders_screen(chat_id, telegram_user_id, filter_key="new", page=0, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    filter_key = filter_key if filter_key in ORDER_FILTERS else "new"
    title, statuses = ORDER_FILTERS[filter_key]
    with session() as db:
        query = db.query(Order)
        if statuses is not None:
            query = query.filter(Order.status.in_(statuses))
        total = query.count()
        max_page = max(0, (total - 1) // PAGE_SIZE)
        page = max(0, min(page, max_page))
        orders = query.order_by(Order.id.desc()).offset(page * PAGE_SIZE).limit(PAGE_SIZE).all()
        rows = [
            [button(
                f"№{order.id} · {status_name(order.status, order.delivery_method)} · {format_money(order.total_price)}",
                f"a:order:{order.id}:{filter_key}",
            )]
            for order in orders
        ]
    filters_row = [
        button(("• " if key == filter_key else "") + label.split(" ", 1)[1], f"a:orders:{key}:0")
        for key, (label, _) in ORDER_FILTERS.items()
    ]
    navigation = []
    if page > 0:
        navigation.append(button("◀️ Назад", f"a:orders:{filter_key}:{page - 1}"))
    if page < max_page:
        navigation.append(button("Вперёд ▶️", f"a:orders:{filter_key}:{page + 1}"))
    text = (
        f"📋 <b>Заказы — {title}</b>\n\n"
        + (f"Найдено: {total} · страница {page + 1} из {max_page + 1}" if total else "Заказов нет.")
    )
    show_screen(chat_id, telegram_user_id, text, inline(filters_row, *rows, navigation, HOME_ROW), message_id)


def admin_order_screen(chat_id, telegram_user_id, order_id, filter_key="new", message_id=None, title=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    with session() as db:
        order = load_order(db, order_id)
        if order is None:
            show_screen(chat_id, telegram_user_id, "Заказ не найден.", inline(HOME_ROW), message_id)
            return
        text = "\n".join(
            [build_order_message(order, title or f"📦 Заказ №{order.id}")]
            + status_history_lines(db, order, show_actor=True)
        )
        keyboard = build_order_keyboard(order.id, order.status, order.delivery_method) or {"inline_keyboard": []}
    rows = keyboard["inline_keyboard"]
    rows.append([button("◀️ К заказам", f"a:orders:{filter_key}:0")])
    rows.append(HOME_ROW)
    show_screen(chat_id, telegram_user_id, text, {"inline_keyboard": rows}, message_id)


def admin_change_status(chat_id, telegram_user_id, order_id, new_status, message_id=None) -> str:
    """Кнопки статуса есть и в уведомлениях, и в карточке заказа."""
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is None or user.role != "ADMIN":
            return "Нужно войти как администратор."
        order = db.query(Order).filter(Order.id == order_id).with_for_update().first()
        if order is None:
            return "Заказ не найден."
        previous_status = get_status_value(order.status)
        delivery_method = order.delivery_method
        if new_status not in allowed_transitions(previous_status, delivery_method):
            return "Статус уже изменён — обнови карточку заказа."
        try:
            change_order_status(order, new_status, db, user.id)
            if new_status == "CANCELLED":
                restore_order_stock(db, order)
            queue_status_changed(db, order, previous_status, new_status, user.id)
            db.commit()
        except HTTPException as error:
            db.rollback()
            return str(error.detail)

    deliver_pending()
    admin_order_screen(
        chat_id, telegram_user_id, order_id, "all", message_id,
        title=f"✅ Заказ №{order_id}: {status_name(new_status, delivery_method)}",
    )
    return f"Заказ №{order_id}: {status_name(new_status, delivery_method)}"


def admin_summary_screen(chat_id, telegram_user_id, message_id=None):
    if require_user(chat_id, telegram_user_id, {"ADMIN"}, message_id) is None:
        return
    now = datetime.now(UTC)
    today_start = now.astimezone(timezone(timedelta(hours=3))).replace(
        hour=0, minute=0, second=0, microsecond=0
    ).astimezone(UTC).replace(tzinfo=None)
    month_start = (now - timedelta(days=30)).replace(tzinfo=None)

    with session() as db:
        created = (
            db.query(OrderStatusHistory.order_id, func.min(OrderStatusHistory.created_at).label("created_at"))
            .group_by(OrderStatusHistory.order_id)
            .subquery()
        )

        def period_stats(start):
            rows = (
                db.query(Order.status, Order.total_price)
                .join(created, created.c.order_id == Order.id)
                .filter(created.c.created_at >= start)
                .all()
            )
            active = [row for row in rows if row.status != "CANCELLED"]
            return len(rows), sum(row.total_price for row in active)

        today_count, today_sum = period_stats(today_start)
        month_count, month_sum = period_stats(month_start)
        new_count = db.query(Order).filter(Order.status == "NEW").count()
        in_work = db.query(Order).filter(Order.status.in_(ORDER_FILTERS["work"][1])).count()
        low_stock = db.query(Product).filter(
            Product.is_active == 1, Product.stock_quantity <= LOW_STOCK_LIMIT
        ).count()

    text = (
        "📊 <b>Сводка</b>\n\n"
        f"Сегодня: {today_count} заказ(ов) на {format_money(today_sum)}\n"
        f"За 30 дней: {month_count} заказ(ов) на {format_money(month_sum)}\n"
        "<i>(сумма без отменённых)</i>\n\n"
        f"🆕 Ждут подтверждения: <b>{new_count}</b>\n"
        f"🔄 В работе: <b>{in_work}</b>\n"
        f"⚠️ Товаров с низким остатком: <b>{low_stock}</b>"
    )
    show_screen(
        chat_id, telegram_user_id, text,
        inline(
            [button("🆕 Новые заказы", "a:orders:new:0"), button("⚠️ Остатки", "a:stock")],
            HOME_ROW,
        ),
        message_id,
    )


def admin_callback_done(chat_id, telegram_user_id, request_id: int, message_id=None) -> str:
    """Кнопка «Перезвонили» под заявкой: отмечает и убирает кнопку."""
    with session() as db:
        user = get_logged_user(db, telegram_user_id)
        if user is None or user.role != "ADMIN":
            return "Нужно войти как администратор."
        request = callbacks.mark_done(db, request_id, user)
        if request is None:
            return "Заявка не найдена."
        who = request.handled_by_label or "администратор"
        text = callbacks.admin_message(request) + f"\n\n✅ <b>Перезвонили</b> · {html.escape(who)}"
    if message_id is not None:
        try:
            edit_message(chat_id, message_id, text, {"inline_keyboard": []})
        except Exception:
            logger.info("Не удалось обновить сообщение о заявке №%s", request_id)
    return "Отмечено: перезвонили"
