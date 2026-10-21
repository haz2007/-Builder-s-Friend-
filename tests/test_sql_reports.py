"""SQL-отчёты (app/sql/*.sql) на данных с заранее известным ответом."""

from datetime import date, datetime, timedelta

from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Order, OrderItem, Product, ProductVariant, User
from app.services import reports


def build_shop(db):
    """Три уровня категорий: Пиломатериалы → Доска → Обрезная доска."""
    lumber = Category(name="Пиломатериалы")
    fasteners = Category(name="Крепёж")
    db.add_all([lumber, fasteners])
    db.flush()
    boards = Category(name="Доска", parent_id=lumber.id)
    db.add(boards)
    db.flush()
    edged = Category(name="Обрезная доска", parent_id=boards.id)
    db.add(edged)
    db.flush()

    products = {}
    for key, name, price, category in [
        ("board", "Доска обрезная", 600, edged),
        ("beam", "Брус", 900, boards),
        ("screw", "Саморезы", 400, fasteners),
        ("nail", "Гвозди", 100, fasteners),
    ]:
        product = Product(name=name, price=price, stock_quantity=10_000, unit="шт",
                          category_id=category.id, is_active=1)
        db.add(product)
        db.flush()
        products[key] = product
    return products


def add_order(db, user, items, created_at, status="DELIVERED", method="DELIVERY"):
    total = sum(product.price * quantity for product, quantity in items)
    order = Order(customer_name="Покупатель", delivery_address="Химки", delivery_method=method,
                  status=status, total_price=total, user_id=user.id, created_at=created_at)
    db.add(order)
    db.flush()
    for product, quantity in items:
        variant = db.query(ProductVariant).filter(ProductVariant.product_id == product.id).first()
        db.add(OrderItem(order_id=order.id, product_id=product.id, variant_id=variant.id,
                         quantity=quantity, price=product.price, unit="шт", base_quantity=1))
    return order


def make_user(db, phone, role="CUSTOMER"):
    user = User(phone=phone, password_hash=hash_password("x"), role=role)
    db.add(user)
    db.flush()
    return user


def test_abc_classes_by_cumulative_share(reset_database):
    db = SessionLocal()
    p = build_shop(db)
    buyer = make_user(db, "+79990000001")
    now = datetime(2026, 10, 15, 12)
    # Выручка: доска 6000 (60 %), брус 2700 (27 %), саморезы 1200 (12 %), гвозди 100 (1 %)
    add_order(db, buyer, [(p["board"], 10), (p["beam"], 3)], now)
    add_order(db, buyer, [(p["screw"], 3), (p["nail"], 1)], now)
    add_order(db, buyer, [(p["board"], 50)], now, status="CANCELLED")  # не считается
    db.commit()

    rows = reports.product_abc(db, None, None)
    db.close()

    assert [(row["name"], row["abc_class"]) for row in rows] == [
        ("Доска обрезная", "A"),  # до неё 0 %
        ("Брус", "A"),            # до него 60 % < 80 %
        ("Саморезы", "B"),        # до них 87 % — между 80 и 95
        ("Гвозди", "C"),          # до них 99 %
    ]
    assert rows[0]["share_pct"] == 60.0
    assert rows[-1]["cumulative_pct"] == 100.0
    assert [row["rank"] for row in rows] == [1, 2, 3, 4]


def test_recursive_rollup_to_root_section(reset_database):
    db = SessionLocal()
    p = build_shop(db)
    buyer = make_user(db, "+79990000002")
    now = datetime(2026, 10, 15, 12)
    add_order(db, buyer, [(p["board"], 1), (p["beam"], 1), (p["screw"], 1)], now)
    db.commit()

    rows = reports.category_revenue(db, None, None)
    db.close()

    # «Обрезная доска» — третий уровень, всё равно попадает в «Пиломатериалы»
    assert rows == [
        {"name": "Пиломатериалы", "revenue": 1500.0},
        {"name": "Крепёж", "revenue": 400.0},
    ]


def test_revenue_series_fills_empty_days(reset_database):
    db = SessionLocal()
    p = build_shop(db)
    buyer = make_user(db, "+79990000003")
    start = datetime(2026, 10, 1)
    add_order(db, buyer, [(p["board"], 1)], start + timedelta(hours=10))
    add_order(db, buyer, [(p["beam"], 1)], start + timedelta(days=4, hours=9))
    db.commit()

    rows = reports.revenue_by_period(db, start, start + timedelta(days=7), "day")
    db.close()

    assert [row["start"] for row in rows] == [f"2026-10-0{day}" for day in range(1, 8)]
    assert [row["revenue"] for row in rows] == [600.0, 0, 0, 0, 900.0, 0, 0]
    assert sum(row["orders"] for row in rows) == 2


def test_monthly_summary_uses_lag_for_growth(reset_database):
    db = SessionLocal()
    p = build_shop(db)
    buyer = make_user(db, "+79990000004")
    add_order(db, buyer, [(p["board"], 10)], datetime(2026, 9, 10))                    # 6000
    add_order(db, buyer, [(p["board"], 10)], datetime(2026, 10, 5), method="PICKUP")   # 6000
    add_order(db, buyer, [(p["beam"], 10)], datetime(2026, 10, 20))                    # 9000
    db.commit()

    rows = reports.monthly_summary(db, date(2026, 10, 21))
    db.close()

    assert [row["month"] for row in rows] == ["2026-09-01", "2026-10-01"]
    assert rows[0]["revenue_change_pct"] is None
    assert rows[1]["revenue"] == 15000.0
    assert rows[1]["revenue_change_pct"] == 150.0   # 15000 к 6000
    assert rows[1]["average_check"] == 7500.0
    assert rows[1]["pickup_pct"] == 50.0


def test_repeat_customers_and_gap(reset_database):
    db = SessionLocal()
    p = build_shop(db)
    loyal = make_user(db, "+79990000005")
    once = make_user(db, "+79990000006")
    add_order(db, loyal, [(p["nail"], 1)], datetime(2026, 10, 1))
    add_order(db, loyal, [(p["nail"], 1)], datetime(2026, 10, 11))  # через 10 дней
    add_order(db, once, [(p["nail"], 1)], datetime(2026, 10, 5))
    db.commit()

    data = reports.repeat_customers(db)
    db.close()

    assert data == {"customers": 2, "repeat_customers": 1, "average_days_between_orders": 10.0}


def test_reports_endpoint_for_admins_only(client: TestClient):
    db = SessionLocal()
    admin = make_user(db, "+79990000007", role="ADMIN")
    customer = make_user(db, "+79990000008")
    db.commit()
    admin_headers = {"Authorization": f"Bearer {create_access_token(user_id=admin.id, role='ADMIN')}"}
    customer_headers = {"Authorization": f"Bearer {create_access_token(user_id=customer.id, role='CUSTOMER')}"}
    db.close()

    data = client.get("/api/v1/admin/reports?period=all", headers=admin_headers).json()

    assert set(data) == {"abc", "monthly", "customers"}
    assert client.get("/api/v1/admin/reports", headers=customer_headers).status_code == 403
