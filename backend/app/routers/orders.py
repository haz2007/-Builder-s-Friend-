import logging

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


logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
)


def restore_order_stock(db: Session, order: Order) -> None:
    """Return product quantities when an order is cancelled."""
    items = list(order.items)
    product_ids = sorted({item.product_id for item in items})

    if not product_ids:
        return

    products = (
        db.query(Product)
        .filter(Product.id.in_(product_ids))
        .order_by(Product.id)
        .with_for_update()
        .populate_existing()
        .all()
    )

    products_by_id = {
        product.id: product
        for product in products
    }

    for item in items:
        product = products_by_id.get(item.product_id)

        if product is None:
            raise HTTPException(
                status_code=409,
                detail=f"Product {item.product_id} no longer exists",
            )

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

        # Check products and combine duplicate product IDs.
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

        # Check stock before deducting anything.
        for product_id, data in products.items():
            product = data["product"]
            quantity = data["quantity"]

            if product.stock_quantity < quantity:
                raise HTTPException(
                    status_code=400,
                    detail=f"Not enough stock for product {product_id}",
                )

        # Create the order.
        order = Order(
            user_id=current_user.id,
            status="NEW",
            total_price=0,
            delivery_address=order_data.delivery_address,
            customer_name=order_data.customer_name.strip(),
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

    # Notify Telegram after the order has been committed.
    try:
        items_text = "\n".join(
            (
                f"• {item.product.name} — "
                f"{item.quantity:g} {item.product.unit} × "
                f"{item.price:g} = "
                f"{item.quantity * item.price:g}"
            )
            for item in order.items
        )

        message = (
            "🛒 Новый заказ — Друг Строителя\n\n"
            f"📦 Заказ №{order.id}\n"
            f"👤 Покупатель: {order.customer_name}\n"
            f"📞 Телефон: {order.user.phone}\n\n"
            f"🧾 Товары:\n{items_text}\n\n"
            f"💰 Итого: {order.total_price:g}\n"
            f"📍 Адрес доставки: "
            f"{order.delivery_address or 'Не указан'}\n"
            f"📌 Статус: {order.status}"
        )

        send_telegram_message(message)

    except Exception:
        logger.exception(
            "Failed to send Telegram notification for order %s",
            order.id,
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
        # Lock the order to prevent simultaneous cancellations.
        order = (
            db.query(Order)
            .filter(Order.id == order_id)
            .with_for_update()
            .populate_existing()
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

        restore_order_stock(db, order)

        change_order_status(
            order,
            "CANCELLED",
            db,
            current_user.id,
        )

        db.commit()
        db.refresh(order)

        return order

    except Exception:
        db.rollback()
        raise


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
        # Lock the order while changing its status.
        order = (
            db.query(Order)
            .filter(Order.id == order_id)
            .with_for_update()
            .populate_existing()
            .first()
        )

        if order is None:
            raise HTTPException(
                status_code=404,
                detail="Order not found",
            )

        # Restore stock if an administrator cancels the order.
        if status_data.status == "CANCELLED":
            restore_order_stock(db, order)

        change_order_status(
            order,
            status_data.status,
            db,
            current_user.id,
        )

        db.commit()
        db.refresh(order)

        return order

    except Exception:
        db.rollback()
        raise


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