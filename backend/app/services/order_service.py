from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Notification, Order, OrderStatusHistory


ALLOWED_TRANSITIONS = {
    "NEW": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"PREPARING", "CANCELLED"},
    "PREPARING": {"READY_FOR_DELIVERY", "CANCELLED"},
    "READY_FOR_DELIVERY": {"ASSIGNED_TO_DRIVER"},
    "ASSIGNED_TO_DRIVER": {"ON_THE_WAY"},
    "ON_THE_WAY": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}


STATUS_MESSAGES = {
    "CONFIRMED": "Ваш заказ подтверждён.",
    "PREPARING": "Ваш заказ готовится.",
    "READY_FOR_DELIVERY": "Ваш заказ готов к доставке.",
    "ASSIGNED_TO_DRIVER": "К вашему заказу назначен водитель.",
    "ON_THE_WAY": "Ваш заказ находится в пути.",
    "DELIVERED": "Ваш заказ доставлен.",
    "CANCELLED": "Ваш заказ отменён.",
}


def change_order_status(
    order: Order,
    new_status: str,
    db: Session | None = None,
    changed_by_user_id: int | None = None,
) -> Order:
    current_status = order.status

    if current_status == new_status:
        raise HTTPException(
            status_code=400,
            detail="Order already has this status",
        )

    allowed_statuses = ALLOWED_TRANSITIONS.get(
        current_status,
        set(),
    )

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status transition: "
                f"{current_status} -> {new_status}"
            ),
        )

    order.status = new_status

    if db is not None:
        history = OrderStatusHistory(
            order_id=order.id,
            status=new_status,
        )

        db.add(history)

        notification = Notification(
            user_id=order.user_id,
            order_id=order.id,
            status=new_status,
            message=STATUS_MESSAGES.get(
                new_status,
                f"Статус заказа изменён на {new_status}.",
            ),
        )

        db.add(notification)

    return order