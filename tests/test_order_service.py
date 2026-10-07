import pytest
from fastapi import HTTPException

from app.models import Order
from app.services.order_service import change_order_status


def create_order(status: str) -> Order:
    return Order(
        status=status,
        total_price=0,
        user_id=1
    )


def test_new_to_confirmed():
    order = create_order("NEW")

    change_order_status(order, "CONFIRMED")

    assert order.status == "CONFIRMED"


def test_confirmed_to_preparing():
    order = create_order("CONFIRMED")

    change_order_status(order, "PREPARING")

    assert order.status == "PREPARING"


def test_preparing_to_ready_for_delivery():
    order = create_order("PREPARING")

    change_order_status(order, "READY_FOR_DELIVERY")

    assert order.status == "READY_FOR_DELIVERY"


def test_ready_for_delivery_to_assigned():
    order = create_order("READY_FOR_DELIVERY")

    change_order_status(order, "ASSIGNED_TO_DRIVER")

    assert order.status == "ASSIGNED_TO_DRIVER"


def test_assigned_to_on_the_way():
    order = create_order("ASSIGNED_TO_DRIVER")

    change_order_status(order, "ON_THE_WAY")

    assert order.status == "ON_THE_WAY"


def test_on_the_way_to_delivered():
    order = create_order("ON_THE_WAY")

    change_order_status(order, "DELIVERED")

    assert order.status == "DELIVERED"


def test_cannot_skip_status():
    order = create_order("NEW")

    with pytest.raises(HTTPException):
        change_order_status(order, "DELIVERED")


def test_cannot_return_to_previous_status():
    order = create_order("PREPARING")

    with pytest.raises(HTTPException):
        change_order_status(order, "CONFIRMED")


def test_cannot_change_delivered_order():
    order = create_order("DELIVERED")

    with pytest.raises(HTTPException):
        change_order_status(order, "CONFIRMED")


def test_cannot_use_same_status():
    order = create_order("NEW")

    with pytest.raises(HTTPException):
        change_order_status(order, "NEW")