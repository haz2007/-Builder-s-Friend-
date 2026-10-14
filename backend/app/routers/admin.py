from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..auth import require_admin
from ..database import get_db
from ..models import Delivery, Order, Product, User


router = APIRouter(
    prefix="/api/v1/admin",
    tags=["Admin"]
)


@router.get("/dashboard")
def get_admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    total_orders = db.query(Order).count()

    new_orders = (
        db.query(Order)
        .filter(Order.status == "NEW")
        .count()
    )

    preparing_orders = (
        db.query(Order)
        .filter(Order.status == "PREPARING")
        .count()
    )

    ready_orders = (
        db.query(Order)
        .filter(Order.status == "READY_FOR_DELIVERY")
        .count()
    )

    delivered_orders = (
        db.query(Order)
        .filter(Order.status == "DELIVERED")
        .count()
    )

    cancelled_orders = (
        db.query(Order)
        .filter(Order.status == "CANCELLED")
        .count()
    )

    total_revenue = (
        db.query(Order)
        .filter(Order.status == "DELIVERED")
        .with_entities(Order.total_price)
        .all()
    )

    revenue = sum(
        order.total_price
        for order in total_revenue
    )

    total_products = db.query(Product).count()

    active_products = (
        db.query(Product)
        .filter(Product.is_active == 1)
        .count()
    )

    low_stock_products = (
        db.query(Product)
        .filter(
            Product.is_active == 1,
            Product.stock_quantity <= 10
        )
        .count()
    )

    total_customers = (
        db.query(User)
        .filter(User.role == "CUSTOMER")
        .count()
    )

    total_drivers = (
        db.query(User)
        .filter(User.role == "DRIVER")
        .count()
    )

    total_deliveries = db.query(Delivery).count()

    waiting_deliveries = (
        db.query(Delivery)
        .filter(Delivery.status == "WAITING")
        .count()
    )

    on_the_way_deliveries = (
        db.query(Delivery)
        .filter(Delivery.status == "ON_THE_WAY")
        .count()
    )

    delivered_deliveries = (
        db.query(Delivery)
        .filter(Delivery.status == "DELIVERED")
        .count()
    )

    return {
        "orders": {
            "total": total_orders,
            "new": new_orders,
            "preparing": preparing_orders,
            "ready_for_delivery": ready_orders,
            "delivered": delivered_orders,
            "cancelled": cancelled_orders
        },
        "revenue": {
            "delivered_orders_revenue": revenue
        },
        "products": {
            "total": total_products,
            "active": active_products,
            "low_stock": low_stock_products
        },
        "users": {
            "customers": total_customers,
            "drivers": total_drivers
        },
        "deliveries": {
            "total": total_deliveries,
            "waiting": waiting_deliveries,
            "on_the_way": on_the_way_deliveries,
            "delivered": delivered_deliveries
        }
    }


@router.get("/products/statistics")
def get_product_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    total_products = db.query(Product).count()

    active_products = (
        db.query(Product)
        .filter(Product.is_active == 1)
        .count()
    )

    inactive_products = (
        db.query(Product)
        .filter(Product.is_active == 0)
        .count()
    )

    low_stock_products = (
        db.query(Product)
        .filter(
            Product.is_active == 1,
            Product.stock_quantity > 0,
            Product.stock_quantity <= 10
        )
        .count()
    )

    out_of_stock_products = (
        db.query(Product)
        .filter(
            Product.is_active == 1,
            Product.stock_quantity == 0
        )
        .count()
    )

    return {
        "total": total_products,
        "active": active_products,
        "inactive": inactive_products,
        "low_stock": low_stock_products,
        "out_of_stock": out_of_stock_products
    }

@router.get("/sales/statistics")
def get_sales_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin)
):
    delivered_orders = (
        db.query(Order)
        .filter(Order.status == "DELIVERED")
        .all()
    )

    total_revenue = sum(
        order.total_price
        for order in delivered_orders
    )

    average_order_value = (
        total_revenue / len(delivered_orders)
        if delivered_orders
        else 0
    )

    cancelled_orders = (
        db.query(Order)
        .filter(Order.status == "CANCELLED")
        .count()
    )

    total_orders = db.query(Order).count()

    conversion_rate = (
        len(delivered_orders) / total_orders * 100
        if total_orders
        else 0
    )

    return {
        "total_orders": total_orders,
        "delivered_orders": len(delivered_orders),
        "cancelled_orders": cancelled_orders,
        "total_revenue": total_revenue,
        "average_order_value": average_order_value,
        "delivery_conversion_rate": conversion_rate
    }