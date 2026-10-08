from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user
from ..database import get_db
from ..models import Order, OrderItem, Product, User
from ..schemas import OrderCreate, OrderResponse, OrderStatusUpdate
from ..services.order_service import change_order_status


router = APIRouter(
    prefix="/api/v1/orders",
    tags=["orders"]
)


@router.post(
    "/",
    response_model=OrderResponse
)
def create_order(
    order_data: OrderCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if not order_data.items:
        raise HTTPException(
            status_code=400,
            detail="Order must contain at least one product"
        )

    order = Order(
        user_id=current_user.id,
        status="NEW",
        total_price=0,
        delivery_address=order_data.delivery_address
    )

    db.add(order)
    total_price = 0

    for item in order_data.items:
        if item.quantity <= 0:
            raise HTTPException(
                status_code=400,
                detail="Quantity must be greater than 0"
            )

        product = (
            db.query(Product)
            .filter(
                Product.id == item.product_id,
                Product.is_active == 1
            )
            .first()
        )

        if product is None:
            raise HTTPException(
                status_code=404,
                detail=f"Product {item.product_id} not found"
            )

        if product.stock_quantity < item.quantity:
            raise HTTPException(
                status_code=400,
                detail=f"Not enough stock for product {product.id}"
            )

        item_total = product.price * item.quantity
        total_price += item_total

        product.stock_quantity -= item.quantity

        order_item = OrderItem(
            order=order,
            product=product,
            quantity=item.quantity,
            price=product.price
        )

        db.add(order_item)

    order.total_price = total_price

    db.commit()
    db.refresh(order)

    return order


@router.get(
    "/",
    response_model=list[OrderResponse]
)
def get_orders(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    query = db.query(Order)

    if current_user.role != "ADMIN":
        query = query.filter(Order.user_id == current_user.id)

    return query.order_by(Order.id.desc()).all()


@router.get(
    "/{order_id}",
    response_model=OrderResponse
)
def get_order(
    order_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    if current_user.role != "ADMIN" and order.user_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="You do not have access to this order"
        )

    return order


@router.patch(
    "/{order_id}/status",
    response_model=OrderResponse
)
def update_order_status(
    order_id: int,
    status_data: OrderStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role != "ADMIN":
        raise HTTPException(
            status_code=403,
            detail="Admin access required"
        )

    order = (
        db.query(Order)
        .filter(Order.id == order_id)
        .first()
    )

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found"
        )

    change_order_status(order, status_data.status)

    db.commit()
    db.refresh(order)

    return order