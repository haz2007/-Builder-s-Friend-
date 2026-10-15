
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
from ..services.order_service import change_order_status


router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
)


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


def notify_telegram(message: str) -> None:
    """Send a Telegram notification without breaking order processing."""
    try:
        send_telegram_message(message)
    except Exception:
        # Telegram errors must not undo a committed order.
        pass



def get_status_value(status) -> str:
    """Возвращает чистый код статуса, даже если передан Enum."""
    return str(getattr(status, "value", status))


STATUS_NAMES = {
    "NEW": "🆕 Новый",
    "CONFIRMED": "✅ Подтверждён",
    "PREPARING": "🪚 Готовится к выдаче",
    "READY_FOR_DELIVERY": "📦 Готов к доставке",
    "ASSIGNED_TO_DRIVER": "🚚 Назначен водитель",
    "ON_THE_WAY": "🛻 В пути",
    "DELIVERED": "🎉 Доставлен",
    "CANCELLED": "❌ Отменён",
}


def build_order_message(order: Order, title: str) -> str:
    """Формирует уведомление о заказе."""
    items_text = "\n".join(
        (
            f"• {item.product.name} — "
            f"{item.quantity:g} {item.product.unit} × "
            f"{item.price:g} = "
            f"{item.quantity * item.price:g}"
        )
        for item in order.items
    )

    status = get_status_value(order.status)
    status_name = STATUS_NAMES.get(status, status)

    return (
        f"{title}\n\n"
        f"📦 Заказ №{order.id}\n"
        f"👤 Покупатель: {order.user.phone or 'Не указан'}\n\n"
        f"🧾 Товары:\n{items_text}\n\n"
        f"💰 Итого: {order.total_price:g}\n"
        f"📍 Адрес доставки: "
        f"{order.delivery_address or 'Не указан'}\n"
        f"📌 Статус: {status_name}"
    )



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

        # Check products and sum quantities for duplicate product IDs.
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

        # Check stock before deducting any products.
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

        # Add order items and deduct stock.
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

    # Notify only after the order has been successfully committed.
    notify_telegram(build_order_message(order, "🛒 Новый заказ — Друг Строителя"))

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

        if order.status != "NEW":
            raise HTTPException(
                status_code=400,
                detail="Only new orders can be cancelled",
            )

        # A NEW order can transition to CANCELLED.
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

    notify_telegram(
        build_order_message(order, "❌ Заказ отменён покупателем")
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

        # Validate and record the transition before changing inventory.
        change_order_status(
            order,
            new_status,
            db,
            current_user.id,
        )

        # Restore stock only when transitioning into CANCELLED.
        if previous_status != "CANCELLED" and new_status == "CANCELLED":
            restore_order_stock(db, order)

        db.commit()
        db.refresh(order)

    except Exception:
        db.rollback()
        raise

    notify_telegram(
        build_order_message(
            order,
            f"🔔 Статус заказа изменён: {previous_status} → {new_status}",
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
