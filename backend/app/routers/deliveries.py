from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..auth import get_current_user, require_admin, require_driver
from ..database import get_db
from ..models import Delivery, Order, User
from ..schemas import (
    DeliveryCreate,
    DeliveryResponse,
    DeliveryStatusUpdate
)


router = APIRouter(
    prefix="/api/v1/deliveries",
    tags=["Deliveries"]
)


@router.post(
    "/{order_id}",
    response_model=DeliveryResponse
)
def create_delivery(
    order_id: int,
    delivery_data: DeliveryCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
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

    existing_delivery = (
        db.query(Delivery)
        .filter(Delivery.order_id == order_id)
        .first()
    )

    if existing_delivery:
        raise HTTPException(
            status_code=400,
            detail="Delivery already exists for this order"
        )

    delivery = Delivery(
        address=delivery_data.address,
        order_id=order_id,
        status="WAITING"
    )

    db.add(delivery)

    db.commit()
    db.refresh(delivery)

    return delivery


@router.get(
    "/",
    response_model=list[DeliveryResponse]
)
def get_deliveries(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    if current_user.role == "ADMIN":
        return db.query(Delivery).all()

    if current_user.role == "DRIVER":
        return (
            db.query(Delivery)
            .filter(Delivery.driver_id == current_user.id)
            .all()
        )

    raise HTTPException(
        status_code=403,
        detail="Access forbidden"
    )


@router.get(
    "/{delivery_id}",
    response_model=DeliveryResponse
)
def get_delivery(
    delivery_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    delivery = (
        db.query(Delivery)
        .filter(Delivery.id == delivery_id)
        .first()
    )

    if delivery is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found"
        )

    if current_user.role == "ADMIN":
        return delivery

    if (
        current_user.role == "DRIVER"
        and delivery.driver_id == current_user.id
    ):
        return delivery

    raise HTTPException(
        status_code=403,
        detail="Access forbidden"
    )


@router.patch(
    "/{delivery_id}/status",
    response_model=DeliveryResponse
)
def update_delivery_status(
    delivery_id: int,
    status_data: DeliveryStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_driver)
):
    delivery = (
        db.query(Delivery)
        .filter(Delivery.id == delivery_id)
        .first()
    )

    if delivery is None:
        raise HTTPException(
        status_code=404,
        detail="Delivery not found"
        )

    if delivery.driver_id != current_user.id:
        raise HTTPException(
            status_code=403,
            detail="This delivery is not assigned to you"
        )

    delivery.status = status_data.status.value

    if status_data.status.value == "ON_THE_WAY":
        delivery.order.status = "ON_THE_WAY"

    if status_data.status.value == "DELIVERED":
        delivery.order.status = "DELIVERED"

    db.commit()
    db.refresh(delivery)

    return delivery


@router.patch(
    "/{delivery_id}/assign/{driver_id}",
    response_model=DeliveryResponse
)
def assign_driver(
    delivery_id: int,
    driver_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    delivery = (
        db.query(Delivery)
        .filter(Delivery.id == delivery_id)
        .first()
    )

    if delivery is None:
        raise HTTPException(
            status_code=404,
            detail="Delivery not found"
        )

    driver = (
        db.query(User)
        .filter(User.id == driver_id)
        .first()
    )

    if driver is None:
        raise HTTPException(
            status_code=404,
            detail="Driver not found"
        )

    if driver.role != "DRIVER":
        raise HTTPException(
            status_code=400,
            detail="Selected user is not a driver"
        )

    delivery.driver_id = driver.id
    delivery.order.status = "ASSIGNED_TO_DRIVER"

    db.commit()
    db.refresh(delivery)

    return delivery