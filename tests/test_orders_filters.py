from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Order, User


def create_admin():
    db = SessionLocal()

    admin = User(
        email="admin_orders_filters@woodcommerce.local",
        password_hash=hash_password("password123"),
        role="ADMIN"
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.close()

    return admin


def create_customer(email):
    db = SessionLocal()

    customer = User(
        email=email,
        password_hash=hash_password("password123"),
        role="CUSTOMER"
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)
    db.close()

    return customer


def create_orders(customer_id):
    db = SessionLocal()

    orders = [
        Order(
            customer_name="Тестовый покупатель",
            user_id=customer_id,
            status="NEW",
            total_price=1000,
            delivery_address="Москва, улица Ленина, 1"
        ),
        Order(
            customer_name="Тестовый покупатель",
            user_id=customer_id,
            status="CONFIRMED",
            total_price=2000,
            delivery_address="Москва, улица Ленина, 2"
        ),
        Order(
            customer_name="Тестовый покупатель",
            user_id=customer_id,
            status="DELIVERED",
            total_price=3000,
            delivery_address="Москва, улица Ленина, 3"
        ),
    ]

    db.add_all(orders)
    db.commit()
    db.close()


def get_token(user):
    return create_access_token(
        user_id=user.id,
        role=user.role
    )


def test_admin_can_filter_orders_by_status(client: TestClient):
    admin = create_admin()
    customer = create_customer(
        "customer_admin_filter@woodcommerce.local"
    )

    create_orders(customer.id)

    token = get_token(admin)

    response = client.get(
        "/api/v1/orders/?status=CONFIRMED",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    orders = response.json()

    assert len(orders) == 1
    assert orders[0]["status"] == "CONFIRMED"


def test_customer_only_sees_own_orders(client: TestClient):
    customer = create_customer(
        "customer_orders_filters@woodcommerce.local"
    )
    other_customer = create_customer(
        "other_customer_orders_filters@woodcommerce.local"
    )

    create_orders(customer.id)
    create_orders(other_customer.id)

    token = get_token(customer)

    response = client.get(
        "/api/v1/orders/",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    orders = response.json()

    assert len(orders) == 3


def test_order_pagination(client: TestClient):
    admin = create_admin()
    customer = create_customer(
        "customer_pagination@woodcommerce.local"
    )

    create_orders(customer.id)

    token = get_token(admin)

    response = client.get(
        "/api/v1/orders/?limit=2&offset=0",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    orders = response.json()

    assert len(orders) == 2


def test_order_status_filter_with_pagination(client: TestClient):
    admin = create_admin()
    customer = create_customer(
        "customer_status_pagination@woodcommerce.local"
    )

    create_orders(customer.id)

    token = get_token(admin)

    response = client.get(
        "/api/v1/orders/?status=NEW&limit=1&offset=0",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    orders = response.json()

    assert len(orders) == 1
    assert orders[0]["status"] == "NEW"
