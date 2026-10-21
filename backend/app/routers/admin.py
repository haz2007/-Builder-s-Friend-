from datetime import date, datetime, time, timedelta

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from ..auth import require_admin
from ..database import get_db
from ..models import (
    Order,
    OrderItem,
    OrderStatusHistory,
    Product,
    User,
)
from ..schemas import as_utc
from ..services import reports

router = APIRouter(prefix="/api/v1/admin", tags=["Admin"])


# Этапы, которые сейчас «в работе» — в порядке движения заказа
PIPELINE_STATUSES = [
    "NEW",
    "CONFIRMED",
    "PREPARING",
    "READY_FOR_DELIVERY",
    "ON_THE_WAY",
]


def _granularity(start: datetime | None, end: datetime | None) -> str:
    """День для короткого периода, неделя для месяца-квартала, месяц для долгого."""
    if start is None or end is None:
        return "month"
    days = (end - start).days
    if days <= 14:
        return "day"
    if days <= 120:
        return "week"
    return "month"


def _date_range(period: str, date_from: date | None, date_to: date | None):
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
    def count(status):
        return db.query(Order).filter(Order.status == status).count()
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
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    start, end = _date_range(period, date_from, date_to)
    granularity = _granularity(start, end)

    base = _filter_dates(db.query(Order), Order.created_at, start, end)
    total = base.count()
    cancelled = base.filter(Order.status == "CANCELLED").count()
    delivered = base.filter(Order.status == "DELIVERED").count()
    not_cancelled = base.filter(Order.status != "CANCELLED")
    not_cancelled_count = not_cancelled.count()

    booked_revenue = float(
        not_cancelled.with_entities(func.coalesce(func.sum(Order.total_price), 0)).scalar() or 0
    )
    delivered_revenue = float(
        base.filter(Order.status == "DELIVERED")
        .with_entities(func.coalesce(func.sum(Order.total_price), 0))
        .scalar()
        or 0
    )

    top_products = _filter_dates(
        db.query(
            Product.id.label("product_id"),
            Product.name.label("name"),
            func.sum(OrderItem.quantity).label("quantity"),
            func.sum(OrderItem.price * OrderItem.quantity).label("revenue"),
        )
        .join(OrderItem, OrderItem.product_id == Product.id)
        .join(Order, Order.id == OrderItem.order_id)
        .filter(Order.status != "CANCELLED"),
        Order.created_at,
        start,
        end,
    )
    top_products = (
        top_products.group_by(Product.id, Product.name)
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

    return {
        "period": period,
        "granularity": granularity,
        # Корзины периода и разделы каталога считает SQL (app/sql/*.sql)
        "revenue_series": reports.revenue_by_period(db, start, end, granularity),
        "category_revenue": reports.category_revenue(db, start, end),
        "pipeline": [
            {"status": status, "count": int(status_counts.get(status, 0))}
            for status in PIPELINE_STATUSES
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
        "top_products": [
            {
                "product_id": p.product_id,
                "name": p.name,
                "quantity": float(p.quantity or 0),
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


@router.get("/reports")
def get_admin_reports(
    period: str = Query("30d", pattern="^(7d|30d|90d|all|custom)$"),
    date_from: date | None = Query(None),
    date_to: date | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    """Отчёты на SQL с CTE и оконными функциями: ABC-анализ, месяцы, повторные покупки."""
    start, end = _date_range(period, date_from, date_to)
    return {
        "abc": reports.product_abc(db, start, end),
        "monthly": reports.monthly_summary(db, date.today()),
        "customers": reports.repeat_customers(db),
    }
