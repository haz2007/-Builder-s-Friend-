from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..services.telegram_service import send_telegram_message
from ..auth import get_current_user
from ..database import get_db
from ..models import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    User,
)
from ..schemas import (
    OrderCreate,
    OrderResponse,
    OrderStatusHistoryResponse,
    OrderStatusUpdate,
)
from ..services.order_service import (
    ALLOWED_TRANSITIONS,
    change_order_status,
)


router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
)


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


def get_status_value(status) -> str:
    """Return the status as a normalized string."""
    value = getattr(status, "value", status)
    return str(value).upper()


def build_order_keyboard(order_id: int, status: str) -> dict | None:
    """Build buttons for valid next actions only."""
    current_status = get_status_value(status)
    next_statuses = ALLOWED_TRANSITIONS.get(current_status, set())

    buttons = []

    for next_status in STATUS_ORDER:
        if next_status in next_statuses:
            buttons.append([
                {
                    "text": ACTION_LABELS[next_status],
                    "callback_data": f"order:{order_id}:{next_status}",
                }
            ])

    if not buttons:
        return None

    return {"inline_keyboard": buttons}


def build_order_message(order: Order, title: str) -> str:
    """Build a formatted Telegram message with order details."""
    status = get_status_value(order.status)
    status_name = STATUS_NAMES.get(status, status)

    customer = getattr(order, "user", None)

    customer_name = (
        getattr(order, "customer_name", None)
        or getattr(customer, "full_name", None)
        or getattr(customer, "name", None)
        or "Имя не указано"
    )

    customer_phone = (
        getattr(order, "customer_phone", None)
        or getattr(customer, "phone", None)
        or "Телефон не указан"
    )

    lines = [
        f"<b>{title}</b>",
        f"📦 Заказ №{order.id}",
        f"👤 Покупатель: {customer_name}",
        f"📞 Телефон: {customer_phone}",
        "",
        "🧾 Товары:",
    ]

    for item in order.items:
        product = getattr(item, "product", None)
        product_name = getattr(product, "name", None) or (
            f"Товар №{item.product_id}"
        )

        lines.append(
            f"• {product_name} × {item.quantity} — "
            f"{item.price} × {item.quantity} = "
            f"{item.price * item.quantity}"
        )

    lines.extend([
        "",
        f"💰 Итого: {order.total_price}",
        f"📍 Адрес доставки: {order.delivery_address or 'Не указан'}",
        f"📌 Статус: {status_name}",
    ])

    return "\n".join(lines)


def notify_telegram(
    message: str,
    reply_markup: dict | None = None,
) -> None:
    """Telegram failures must not break order processing."""
    try:
        send_telegram_message(
            message,
            reply_markup=reply_markup,
        )
    except Exception:
        import logging
        logging.exception("Не удалось отправить уведомление в Telegram")


def restore_order_stock(db: Session, order: Order) -> None:
    """Return products from a cancelled order to store inventory."""
    for item in order.items:
        product = (
            db.query(Product)
            .filter(Product.id == item.product_id)
            .with_for_update()
            .first()
        )

        if product is not None:
            product.stock_quantity += item.quantity


@router.post("/", response_model=OrderResponse)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not order_data.items:
        raise HTTPException(
            status_code=400,
            detail="Order must contain at least one product",
        )

    try:
        products = {}

        # Validate products and combine duplicate product IDs.
        for item in order_data.items:
            if item.quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Quantity must be greater than 0",
                )

            product = (
                db.query(Product)
                .filter(
                    Product.id == item.product_id,
                    Product.is_active == 1,
                )
                .with_for_update()
                .first()
            )

            if product is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product {item.product_id} not found",
                )

            if item.product_id not in products:
                products[item.product_id] = {
                    "product": product,
                    "quantity": 0,
                }

            products[item.product_id]["quantity"] += item.quantity

        # Check all stock levels before deducting anything.
        for product_id, data in products.items():
            product = data["product"]
            quantity = data["quantity"]

            if product.stock_quantity < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough stock for product {product_id}",
                )

        order = Order(
            user_id=current_user.id,
            customer_name=order_data.customer_name.strip(),
            status="NEW",
            total_price=0,
            delivery_address=order_data.delivery_address,
        )

        db.add(order)
        db.flush()

        db.add(
            OrderStatusHistory(
                order_id=order.id,
                status="NEW",
            )
        )

        total_price = 0

        for data in products.values():
            product = data["product"]
            quantity = data["quantity"]

            total_price += product.price * quantity
            product.stock_quantity -= quantity

            db.add(
                OrderItem(
                    order=order,
                    product=product,
                    quantity=quantity,
                    price=product.price,
                )
            )

        order.total_price = total_price

        db.commit()
        db.refresh(order)

    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise

    # New-order message: retain admin action buttons.
    notify_telegram(
        build_order_message(
            order,
            "🛒 Новый заказ — Друг Строителя",
            ),
        )

    return order


@router.get("/", response_model=list[OrderResponse])
def get_orders(
    status: str | None = Query(
        default=None,
        min_length=1,
        max_length=50,
    ),
    limit: int = Query(default=20, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    query = db.query(Order)

    if current_user.role != "ADMIN":
        query = query.filter(Order.user_id == current_user.id)

    if status is not None:
        query = query.filter(Order.status == status)

    return (
        query
        .order_by(Order.id.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    if (
        current_user.role != "ADMIN"
        and order.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this order",
        )

    return order


@router.get(
    "/{order_id}/history",
    response_model=list[OrderStatusHistoryResponse],
)
def get_order_history(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found",
        )

    if (
        current_user.role != "ADMIN"
        and order.user_id != current_user.id
    ):
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this order",
        )

    return (
        db.query(OrderStatusHistory)
        .filter(OrderStatusHistory.order_id == order_id)
        .order_by(OrderStatusHistory.id.asc())
        .all()
    )


@router.post("/{order_id}/cancel", response_model=OrderResponse)
def cancel_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    try:
        order = (
            db.query(Order)
            .filter(Order.id == order_id)
            .with_for_update()
            .first()
        )

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        if order.user_id != current_user.id:
            raise HTTPException(
                status_code=403,
                detail="You do not have access to this order",
            )

        if get_status_value(order.status) != "NEW":
            raise HTTPException(
                status_code=400,
                detail="Only new orders can be cancelled",
            )

        change_order_status(
            order,
            "CANCELLED",
            db,
            current_user.id,
        )

        restore_order_stock(db, order)

        db.commit()
        db.refresh(order)

    except Exception:
        db.rollback()
        raise

    # Cancellation notification: no buttons.
    notify_telegram(
        build_order_message(
            order,
            "❌ Заказ отменён покупателем",
        )
    )

    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_data: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    try:
        order = (
            db.query(Order)
            .filter(Order.id == order_id)
            .with_for_update()
            .first()
        )

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        previous_status = get_status_value(order.status)
        new_status = get_status_value(status_data.status)

        change_order_status(
            order,
            new_status,
            db,
            current_user.id,
        )

        if previous_status != "CANCELLED" and new_status == "CANCELLED":
            restore_order_stock(db, order)

        db.commit()
        db.refresh(order)

    except Exception:
        db.rollback()
        raise

    # Status-update notification: deliberately no reply_markup.
    notify_telegram(
        build_order_message(
            order,
            f"🔔 Статус заказа изменён: "
            f"{STATUS_NAMES.get(previous_status, previous_status)} → "
            f"{STATUS_NAMES.get(new_status, new_status)}",
        )
    )

    return order


@router.get("/admin/new-count")
def get_new_orders_count(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Admin access required",
        )

    count = (
        db.query(Order)
        .filter(Order.status == "NEW")
        .count()
    )

    return {"new_orders_count": count}
