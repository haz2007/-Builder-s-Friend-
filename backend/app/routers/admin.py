from datetime import date, datetime, time, timedelta
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..auth import require_admin
from ..database import get_db
from ..schemas import as_utc
from ..models import (
    Category,
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    User,
)

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# Этапы, которые сейчас «в работе» — в порядке движения заказа
PIPELINE_STATUSES = [
    "NEW",
    "CONFIRMED",
    "PREPARING",
    "READY_FOR_DELIVERY",
    "ON_THE_WAY",
]


def _granularity(start: Optional[datetime], end: Optional[datetime]) -> str:
    """День для короткого периода, неделя для месяца-квартала, месяц для долгого."""
    if start is None or end is None:
        return "month"
    days = (end - start).days
    if days <= 14:
        return "day"
    if days <= 120:
        return "week"
    return "month"


def _bucket_start(day: date, granularity: str) -> date:
    if granularity == "week":
        return day - timedelta(days=day.weekday())
    if granularity == "month":
        return day.replace(day=1)
    return day


def _next_bucket(day: date, granularity: str) -> date:
    if granularity == "day":
        return day + timedelta(days=1)
    if granularity == "week":
        return day + timedelta(days=7)
    return (day.replace(day=28) + timedelta(days=4)).replace(day=1)


def _revenue_series(rows, start, end, granularity: str) -> list[dict]:
    """Выручка без отмен по корзинам периода; пустые корзины тоже есть."""
    buckets: dict[date, dict] = {}
    for order_date, status, total_price in rows:
        key = _bucket_start(order_date.date(), granularity)
        item = buckets.setdefault(key, {"revenue": 0.0, "orders": 0})
        if status != "CANCELLED":
            item["revenue"] += float(total_price or 0)
            item["orders"] += 1

    if not buckets and start is None:
        return []

    first = _bucket_start(start.date(), granularity) if start else min(buckets)
    last = (end - timedelta(days=1)).date() if end else max(buckets)

    series = []
    cursor = first
    while cursor <= last:
        following = _next_bucket(cursor, granularity)
        item = buckets.get(cursor, {"revenue": 0.0, "orders": 0})
        series.append({
            "start": cursor.isoformat(),
            "end": (following - timedelta(days=1)).isoformat(),
            "revenue": round(item["revenue"], 2),
            "orders": item["orders"],
        })
        cursor = following
    return series


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


@router.get("/activity")
def get_activity(
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Журнал: кто и когда менял статусы заказов (новые сверху)."""
    from ..services.order_notifications import status_name

    entries = (
        db.query(OrderStatusHistory)
        .options(joinedload(OrderStatusHistory.order), joinedload(OrderStatusHistory.changed_by))
        .order_by(OrderStatusHistory.created_at.desc(), OrderStatusHistory.id.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": entry.id,
            "order_id": entry.order_id,
            "status": entry.status,
            "status_name": status_name(entry.status, entry.order.delivery_method),
            "created_at": as_utc(entry.created_at),
            "changed_by": entry.changed_by_label,
            "customer_name": entry.order.customer_name,
            "total_price": entry.order.total_price,
        }
        for entry in entries
    ]


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
            "admins": db.query(User).filter(User.role == "ADMIN").count(),
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

    # Заказы на каждом этапе прямо сейчас (не зависит от периода)
    status_counts = dict(
        db.query(Order.status, func.count(Order.id))
        .filter(Order.status.in_(PIPELINE_STATUSES))
        .group_by(Order.status)
        .all()
    )

    # Выручка по разделам каталога (подкатегории сворачиваются в раздел)
    categories = {category.id: category for category in db.query(Category).all()}
    category_query = (
        db.query(
            Product.category_id,
            func.sum(OrderItem.price * OrderItem.quantity),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .join(first_status, first_status.c.order_id == Order.id)
        .filter(Order.status != "CANCELLED")
    )
    if start is not None:
        category_query = category_query.filter(
            first_status.c.order_date >= start,
            first_status.c.order_date < end,
        )
    by_section: dict[str, float] = {}
    for category_id, revenue in category_query.group_by(Product.category_id).all():
        category = categories.get(category_id)
        if category is not None and category.parent_id in categories:
            category = categories[category.parent_id]
        name = category.name if category else "Без раздела"
        by_section[name] = by_section.get(name, 0.0) + float(revenue or 0)

    granularity = _granularity(start, end)

    return {
        "period": period,
        "granularity": granularity,
        "revenue_series": _revenue_series(rows, start, end, granularity),
        "pipeline": [
            {"status": status, "count": int(status_counts.get(status, 0))}
            for status in PIPELINE_STATUSES
        ],
        "category_revenue": [
            {"name": name, "revenue": round(revenue, 2)}
            for name, revenue in sorted(by_section.items(), key=lambda item: -item[1])
        ],
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
