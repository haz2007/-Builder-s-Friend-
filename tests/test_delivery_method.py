from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, User


def setup_order_data():
    db = SessionLocal()
    customer = User(
        phone="+79990001122",
        password_hash=hash_password("password123"),
        role="CUSTOMER",
    )
    category = Category(name="Крепёж")
    db.add_all([customer, category])
    db.commit()
    product = Product(
        name="Саморез",
        price=100,
        stock_quantity=50,
        unit="кг",
        category_id=category.id,
    )
    db.add(product)
    db.commit()
    token = create_access_token(user_id=customer.id, role=customer.role)
    product_id = product.id
    db.close()
    return {"Authorization": f"Bearer {token}"}, product_id


def test_pickup_order_without_address(client: TestClient):
    headers, product_id = setup_order_data()

    response = client.post(
        "/api/v1/orders/",
        json={
            "customer_name": "Покупатель",
            "delivery_method": "PICKUP",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
        headers=headers,
    )

    assert response.status_code == 200
    data = response.json()
    assert data["delivery_method"] == "PICKUP"
    assert data["delivery_address"] == "Самовывоз со склада"


def test_delivery_requires_address(client: TestClient):
    headers, product_id = setup_order_data()

    response = client.post(
        "/api/v1/orders/",
        json={
            "customer_name": "Покупатель",
            "delivery_method": "DELIVERY",
            "delivery_address": "",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
        headers=headers,
    )

    assert response.status_code == 422


def test_delivery_is_default(client: TestClient):
    headers, product_id = setup_order_data()

    response = client.post(
        "/api/v1/orders/",
        json={
            "customer_name": "Покупатель",
            "delivery_address": "Москва, улица Ленина, 1",
            "items": [{"product_id": product_id, "quantity": 1}],
        },
        headers=headers,
    )

    assert response.status_code == 200
    assert response.json()["delivery_method"] == "DELIVERY"
