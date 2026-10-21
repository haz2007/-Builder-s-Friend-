from fastapi import HTTPException
from sqlalchemy.orm import Session

from ..models import Notification, Order, OrderStatusHistory

# Доставка: собранный заказ везут покупателю
ALLOWED_TRANSITIONS = {
    "NEW": {"CONFIRMED", "CANCELLED"},
    "CONFIRMED": {"PREPARING", "CANCELLED"},
    "PREPARING": {"READY_FOR_DELIVERY", "CANCELLED"},
    "READY_FOR_DELIVERY": {"ON_THE_WAY", "CANCELLED"},
    "ON_THE_WAY": {"DELIVERED"},
    "DELIVERED": set(),
    "CANCELLED": set(),
}

# Самовывоз: покупатель сам забирает собранный заказ — этапа «В пути» нет,
# «Готов к выдаче» → «Выдан»
PICKUP_TRANSITIONS = {
    **ALLOWED_TRANSITIONS,
    "READY_FOR_DELIVERY": {"DELIVERED", "CANCELLED"},
}

STATUS_MESSAGES = {
    "NEW": "Ваш заказ оформлен.",
    "CONFIRMED": "Ваш заказ подтверждён.",
    "PREPARING": "Ваш заказ готовится.",
    "READY_FOR_DELIVERY": "Ваш заказ готов к доставке.",
    "ON_THE_WAY": "Ваш заказ в пути.",
    "DELIVERED": "Ваш заказ доставлен.",
    "CANCELLED": "Ваш заказ отменён.",
}

PICKUP_STATUS_MESSAGES = {
    **STATUS_MESSAGES,
    "READY_FOR_DELIVERY": "Ваш заказ собран — можно забирать со склада.",
    "DELIVERED": "Заказ выдан. Спасибо за покупку!",
}


def allowed_transitions(status, delivery_method: str | None = None) -> set[str]:
    """Куда можно перевести заказ из статуса status с учётом способа получения."""
    table = PICKUP_TRANSITIONS if delivery_method == "PICKUP" else ALLOWED_TRANSITIONS
    return table.get(get_status_value(status), set())


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

    if current_status not in ALLOWED_TRANSITIONS:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown current order status: {current_status}",
        )

    if new_status not in allowed_transitions(current_status, order.delivery_method):
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
            changed_by_id=user_id,
        )
    )

    messages = PICKUP_STATUS_MESSAGES if order.delivery_method == "PICKUP" else STATUS_MESSAGES
    message = messages.get(
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
