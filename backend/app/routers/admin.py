from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from ..auth import require_admin
from ..database import get_db
from ..models import (
    Delivery,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    User,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


def _date_range(period: str, date_from: Optional[date], date_to: Optional[date]):
    today = date.today()
    if period == "custom":
        if not date_from or not date_to:
            raise HTTPException(400, "Для произвольного периода укажи обе даты.")
        if date_from > date_to:
            raise HTTPException(400, "Дата начала не может быть позже даты окончания.")
        return (
            datetime.combine(date_from, time.min),
            datetime.combine(date_to + timedelta(days=1), time.min),
        )

    days = {"7d": 7, "30d": 30, "90d": 90}
    if period == "all":
        return None, None
    if period not in days:
        raise HTTPException(400, "Неизвестный период.")

    start = today - timedelta(days=days[period] - 1)
    return (
        datetime.combine(start, time.min),
        datetime.combine(today + timedelta(days=1), time.min),
    )


def _filter_dates(query, column, start, end):
    if start is None:
        return query
    return query.filter(column >= start, column < end)


def _order_first_status_subquery(db: Session):
    """One timestamp per order: its earliest recorded status-history entry."""
    return (
        db.query(
            OrderStatusHistory.order_id.label("order_id"),
            func.min(OrderStatusHistory.created_at).label("order_date"),
        )
        .group_by(OrderStatusHistory.order_id)
        .subquery()
    )


@router.get("/dashboard")
def get_admin_dashboard(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    total_orders = db.query(Order).count()
    count = lambda status: db.query(Order).filter(Order.status == status).count()
    delivered_revenue = (
        db.query(func.coalesce(func.sum(Order.total_price), 0))
        .filter(Order.status == "DELIVERED")
        .scalar()
    )
    total_products = db.query(Product).count()
    active_products = db.query(Product).filter(Product.is_active == 1).count()
    low_stock_products = (
        db.query(Product)
        .filter(Product.is_active == 1, Product.stock_quantity <= 10)
        .count()
    )
    total_deliveries = db.query(Delivery).count()
    return {
        "orders": {
            "total": total_orders,
            "new": count("NEW"),
            "preparing": count("PREPARING"),
            "ready_for_delivery": count("READY_FOR_DELIVERY"),
            "delivered": count("DELIVERED"),
            "cancelled": count("CANCELLED"),
        },
        "revenue": {"delivered_orders_revenue": float(delivered_revenue or 0)},
        "products": {
            "total": total_products,
            "active": active_products,
            "low_stock": low_stock_products,
        },
        "users": {
            "customers": db.query(User).filter(User.role == "CUSTOMER").count(),
            "drivers": db.query(User).filter(User.role == "DRIVER").count(),
        },
        "deliveries": {
            "total": total_deliveries,
            "waiting": db.query(Delivery).filter(Delivery.status == "WAITING").count(),
            "on_the_way": db.query(Delivery).filter(Delivery.status == "ON_THE_WAY").count(),
            "delivered": db.query(Delivery).filter(Delivery.status == "DELIVERED").count(),
        },
    }


@router.get("/products/statistics")
def get_product_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    return {
        "total": db.query(Product).count(),
        "active": db.query(Product).filter(Product.is_active == 1).count(),
        "inactive": db.query(Product).filter(Product.is_active == 0).count(),
        "low_stock": db.query(Product)
        .filter(
            Product.is_active == 1,
            Product.stock_quantity > 0,
            Product.stock_quantity <= 10,
        )
        .count(),
        "out_of_stock": db.query(Product)
        .filter(Product.is_active == 1, Product.stock_quantity == 0)
        .count(),
    }


@router.get("/sales/statistics")
def get_sales_statistics(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    delivered = db.query(Order).filter(Order.status == "DELIVERED").all()
    revenue = sum(float(order.total_price or 0) for order in delivered)
    cancelled = db.query(Order).filter(Order.status == "CANCELLED").count()
    total = db.query(Order).count()
    return {
        "total_orders": total,
        "delivered_orders": len(delivered),
        "cancelled_orders": cancelled,
        "total_revenue": revenue,
        "average_order_value": revenue / len(delivered) if delivered else 0,
        "delivery_conversion_rate": len(delivered) / total * 100 if total else 0,
    }


@router.get("/analytics")
def get_admin_analytics(
    period: str = Query("30d", pattern="^(7d|30d|90d|all|custom)$"),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    start, end = _date_range(period, date_from, date_to)
    first_status = _order_first_status_subquery(db)

    # Join to a subquery with one row per order, avoiding duplicates caused
    # by orders having multiple status-history records.
    base = db.query(Order).join(
        first_status, first_status.c.order_id == Order.id
    )
    base = _filter_dates(base, first_status.c.order_date, start, end)

    total = base.count()
    cancelled = base.filter(Order.status == "CANCELLED").count()
    delivered = base.filter(Order.status == "DELIVERED").count()
    not_cancelled = base.filter(Order.status != "CANCELLED")
    not_cancelled_count = not_cancelled.count()

    booked_revenue = float(
        not_cancelled.with_entities(
            func.coalesce(func.sum(Order.total_price), 0)
        ).scalar()
        or 0
    )
    delivered_revenue = float(
        base.filter(Order.status == "DELIVERED")
        .with_entities(func.coalesce(func.sum(Order.total_price), 0))
        .scalar()
        or 0
    )

    rows = (
        db.query(
            first_status.c.order_date,
            Order.status,
            Order.total_price,
        )
        .join(first_status, first_status.c.order_id == Order.id)
        .filter(
            first_status.c.order_date >= start if start is not None else True
        )
        .filter(first_status.c.order_date < end if end is not None else True)
        .order_by(first_status.c.order_date.asc())
        .all()
    )

    trend_map = {}
    for order_date, status, total_price in rows:
        day = order_date.date().isoformat()
        item = trend_map.setdefault(
            day,
            {
                "date": day,
                "orders": 0,
                "revenue": 0.0,
                "delivered_revenue": 0.0,
            },
        )
        item["orders"] += 1
        if status != "CANCELLED":
            item["revenue"] += float(total_price or 0)
        if status == "DELIVERED":
            item["delivered_revenue"] += float(total_price or 0)

    if start is not None:
        cursor, last = start.date(), (end - timedelta(days=1)).date()
        while cursor <= last:
            trend_map.setdefault(
                cursor.isoformat(),
                {
                    "date": cursor.isoformat(),
                    "orders": 0,
                    "revenue": 0.0,
                    "delivered_revenue": 0.0,
                },
            )
            cursor += timedelta(days=1)

    product_query = (
        db.query(
            Product.id.label("product_id"),
            Product.name.label("name"),
            func.sum(OrderItem.quantity).label("quantity"),
            func.sum(OrderItem.price * OrderItem.quantity).label("revenue"),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(first_status, first_status.c.order_id == Order.id)
        .filter(Order.status != "CANCELLED")
    )
    if start is not None:
        product_query = product_query.filter(
            first_status.c.order_date >= start,
            first_status.c.order_date < end,
        )

    top_products = (
        product_query.group_by(Product.id, Product.name)
        .order_by(func.sum(OrderItem.quantity).desc())
        .limit(5)
        .all()
    )
    low_stock = (
        db.query(Product)
        .filter(Product.is_active == 1, Product.stock_quantity <= 10)
        .order_by(Product.stock_quantity.asc())
        .limit(10)
        .all()
    )

    return {
        "period": period,
        "date_from": start.date().isoformat() if start else None,
        "date_to": (end - timedelta(days=1)).date().isoformat() if end else None,
        "orders": {
            "total": total,
            "cancelled": cancelled,
            "delivered": delivered,
            "not_cancelled": not_cancelled_count,
        },
        "revenue": {
            "not_cancelled": booked_revenue,
            "delivered": delivered_revenue,
        },
        "average_order_value": (
            booked_revenue / not_cancelled_count if not_cancelled_count else 0
        ),
        "delivery_conversion_rate": delivered / total * 100 if total else 0,
        "trend": [trend_map[key] for key in sorted(trend_map)],
        "top_products": [
            {
                "product_id": p.product_id,
                "name": p.name,
                "quantity": int(p.quantity or 0),
                "revenue": float(p.revenue or 0),
            }
            for p in top_products
        ],
        "low_stock_products": [
            {
                "id": p.id,
                "name": p.name,
                "stock_quantity": float(p.stock_quantity or 0),
                "unit": p.unit,
            }
            for p in low_stock
        ],
    }
