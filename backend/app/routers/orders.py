from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from sqlalchemy.orm import Session

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
from ..services.order_notifications import (
    notify_order_cancelled_by_customer,
    notify_order_created,
    notify_order_status_changed,
)
from ..services.order_service import (
    change_order_status,
    get_status_value,
)
from ..services.variant_service import (
    get_primary_variant,
    requires_whole_quantity,
    restore_order_stock,
)


router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"],
)


@router.post("/", response_model=OrderResponse)
def create_order(
    order_data: OrderCreate,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    if not order_data.items:
        raise HTTPException(
            status_code=400,
            detail="Order must contain at least one product",
        )

    try:
        variants = {}

        # Блокируем все товары заказа одним запросом в порядке id:
        # при одинаковом порядке параллельные заказы не ловят deadlock
        product_ids = sorted({item.product_id for item in order_data.items})
        locked_products = {
            product.id: product
            for product in (
                db.query(Product)
                .filter(Product.id.in_(product_ids), Product.is_active == 1)
                .order_by(Product.id)
                .with_for_update()
                .all()
            )
        }

        # Validate products/variants and combine duplicate variants.
        for item in order_data.items:
            if item.quantity <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Quantity must be greater than 0",
                )

            product = locked_products.get(item.product_id)

            if product is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Product {item.product_id} not found",
                )

            if item.variant_id is None:
                variant = get_primary_variant(product)
            else:
                variant = next(
                    (v for v in product.variants if v.id == item.variant_id),
                    None,
                )

            if variant is None or variant.is_active != 1:
                raise HTTPException(
                    status_code=404,
                    detail=(
                        f"Variant {item.variant_id} of product "
                        f"{item.product_id} not found"
                    ),
                )

            if (
                requires_whole_quantity(product, variant)
                and item.quantity != int(item.quantity)
            ):
                raise HTTPException(
                    status_code=400,
                    detail=(
                        f"«{product.name}» продаётся только целым "
                        f"количеством ({variant.unit})"
                    ),
                )

            if variant.id not in variants:
                variants[variant.id] = {
                    "product": product,
                    "variant": variant,
                    "quantity": 0,
                }

            variants[variant.id]["quantity"] += item.quantity

        # Склад общий для всех вариантов товара: 4 м³ по 27 шт = 108 шт.
        needed_by_product = {}
        for data in variants.values():
            product = data["product"]
            needed = data["quantity"] * data["variant"].base_quantity
            needed_by_product[product.id] = (
                needed_by_product.get(product.id, 0) + needed
            )

        # Check all stock levels before deducting anything.
        for product_id, needed in needed_by_product.items():
            product = next(
                data["product"]
                for data in variants.values()
                if data["product"].id == product_id
            )
            if product.stock_quantity < needed:
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
            delivery_method=order_data.delivery_method,
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

        for data in variants.values():
            product = data["product"]
            variant = data["variant"]
            quantity = data["quantity"]

            total_price += variant.price * quantity
            product.stock_quantity -= quantity * variant.base_quantity

            db.add(
                OrderItem(
                    order=order,
                    product=product,
                    variant=variant,
                    quantity=quantity,
                    price=variant.price,
                    unit=variant.unit,
                    base_quantity=variant.base_quantity,
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

    background_tasks.add_task(notify_order_created, order.id)

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
    background_tasks: BackgroundTasks,
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

    background_tasks.add_task(notify_order_cancelled_by_customer, order.id)

    return order


@router.patch("/{order_id}/status", response_model=OrderResponse)
def update_order_status(
    order_id: int,
    status_data: OrderStatusUpdate,
    background_tasks: BackgroundTasks,
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

    background_tasks.add_task(
        notify_order_status_changed,
        order.id,
        previous_status,
        new_status,
        current_user.id,
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
