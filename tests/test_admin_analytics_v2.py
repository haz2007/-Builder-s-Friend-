from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, User


def setup_shop():
    db = SessionLocal()
    admin = User(email="admin@woodcommerce.local", password_hash=hash_password("x"), role="ADMIN")
    customer = User(phone="+79990001122", password_hash=hash_password("x"), role="CUSTOMER")
    lumber = Category(name="Пиломатериалы")
    db.add_all([admin, customer, lumber])
    db.commit()
    boards = Category(name="Доска", parent_id=lumber.id)
    db.add(boards)
    db.commit()
    product = Product(name="Доска 50×150", price=600, stock_quantity=100, unit="шт", category_id=boards.id)
    db.add(product)
    db.commit()
    result = (
        {"Authorization": f"Bearer {create_access_token(user_id=admin.id, role='ADMIN')}"},
        {"Authorization": f"Bearer {create_access_token(user_id=customer.id, role='CUSTOMER')}"},
        product.id,
    )
    db.close()
    return result


def order(client, headers, product_id, quantity):
    return client.post(
        "/api/v1/orders/",
        json={
            "customer_name": "Покупатель",
            "delivery_method": "PICKUP",
            "items": [{"product_id": product_id, "quantity": quantity}],
        },
        headers=headers,
    ).json()


def test_new_order_allows_only_confirm_or_cancel(client: TestClient):
    _, customer, product_id = setup_shop()

    data = order(client, customer, product_id, 1)

    assert data["allowed_statuses"] == ["CONFIRMED", "CANCELLED"]


def test_on_the_way_allows_only_delivered(client: TestClient):
    admin, customer, product_id = setup_shop()
    order_id = order(client, customer, product_id, 1)["id"]

    for status in ["CONFIRMED", "PREPARING", "READY_FOR_DELIVERY"]:
        client.patch(f"/api/v1/orders/{order_id}/status", json={"status": status}, headers=admin)
    data = client.patch(
        f"/api/v1/orders/{order_id}/status", json={"status": "ON_THE_WAY"}, headers=admin
    ).json()

    assert data["allowed_statuses"] == ["DELIVERED"]


def test_analytics_series_pipeline_and_sections(client: TestClient):
    admin, customer, product_id = setup_shop()
    first = order(client, customer, product_id, 2)
    order(client, customer, product_id, 1)
    client.patch(f"/api/v1/orders/{first['id']}/status", json={"status": "CONFIRMED"}, headers=admin)

    data = client.get("/api/v1/admin/analytics?period=7d", headers=admin).json()

    assert data["granularity"] == "day"
    assert len(data["revenue_series"]) == 7
    assert sum(bucket["revenue"] for bucket in data["revenue_series"]) == 1800
    assert sum(bucket["orders"] for bucket in data["revenue_series"]) == 2

    pipeline = {row["status"]: row["count"] for row in data["pipeline"]}
    assert pipeline["NEW"] == 1
    assert pipeline["CONFIRMED"] == 1

    # Подкатегория «Доска» сворачивается в раздел «Пиломатериалы»
    assert data["category_revenue"] == [{"name": "Пиломатериалы", "revenue": 1800}]


def test_analytics_uses_weeks_for_30_days(client: TestClient):
    admin, _, _ = setup_shop()

    data = client.get("/api/v1/admin/analytics?period=30d", headers=admin).json()

    assert data["granularity"] == "week"
    assert 4 <= len(data["revenue_series"]) <= 6
