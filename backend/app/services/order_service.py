from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Order, OrderStatusHistory, Notification


ALLOWED_TRANSITIONS = {
    "NEW": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"PREPARING", "CANCELLED"},
    "PREPARING": {"READY_FOR_DELIVERY", "CANCELLED"},
    "READY_FOR_DELIVERY": {"ASSIGNED_TO_DRIVER", "CANCELLED"},
    "ASSIGNED_TO_DRIVER": {"ON_THE_WAY", "CANCELLED"},
    "ON_THE_WAY": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}

STATUS_MESSAGES = {
    "NEW": "Ваш заказ оформлен.",
    "CONFIRMED": "Ваш заказ подтверждён.",
    "PREPARING": "Ваш заказ готовится.",
    "READY_FOR_DELIVERY": "Ваш заказ готов к доставке.",
    "ASSIGNED_TO_DRIVER": "Для вашего заказа назначен водитель.",
    "ON_THE_WAY": "Ваш заказ в пути.",
    "DELIVERED": "Ваш заказ доставлен.",
    "CANCELLED": "Ваш заказ отменён.",
}


def get_status_value(status) -> str:
    value = getattr(status, "value", status)
    return str(value).upper()


def change_order_status(
    order: Order,
    new_status: str,
    db: Session,
    user_id: int,
) -> None:
    """Изменяет статус заказа и создаёт уведомление покупателю."""

    current_status = get_status_value(order.status)
    new_status = get_status_value(new_status)

    allowed_statuses = ALLOWED_TRANSITIONS.get(current_status)

    if allowed_statuses is None:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown current order status: {current_status}",
        )

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Cannot change order status "
                f"from {current_status} to {new_status}"
            ),
        )

    order.status = new_status

    db.add(
        OrderStatusHistory(
            order_id=order.id,
            status=new_status,
        )
    )

    message = STATUS_MESSAGES.get(
        new_status,
        "Статус вашего заказа обновлён.",
    )

    db.add(
        Notification(
            user_id=order.user_id,
            order_id=order.id,
            status=new_status,
            message=message,
            is_read=0,
        )
    )
