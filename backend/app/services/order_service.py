from fastapi import HTTPException

from ..models import Order


ALLOWED_TRANSITIONS = {
    "NEW": {
        "CONFIRMED",
        "CANCELLED",
    },
    "CONFIRMED": {
        "PREPARING",
        "CANCELLED",
    },
    "PREPARING": {
        "READY_FOR_DELIVERY",
        "CANCELLED",
    },
    "READY_FOR_DELIVERY": {
        "ASSIGNED_TO_DRIVER",
    },
    "ASSIGNED_TO_DRIVER": {
        "ON_THE_WAY",
    },
    "ON_THE_WAY": {
        "DELIVERED",
    },
    "DELIVERED": set(),
    "CANCELLED": set(),
}


def change_order_status(
    order: Order,
    new_status: str
) -> Order:
    current_status = order.status

    if current_status == new_status:
        raise HTTPException(
            status_code=400,
            detail="Order already has this status"
        )

    allowed_statuses = ALLOWED_TRANSITIONS.get(
        current_status,
        set()
    )

    if new_status not in allowed_statuses:
        raise HTTPException(
            status_code=400,
            detail=(
                f"Invalid status transition: "
                f"{current_status} -> {new_status}"
            )
        )

    order.status = new_status

    return order