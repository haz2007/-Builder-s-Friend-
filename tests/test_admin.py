from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Order, Product, User


def create_user(email: str, role: str):
    db = SessionLocal()

    user = User(
        email=email,
        password_hash=hash_password("password123"),
        role=role
    )

    db.add(user)
    db.commit()
    db.refresh(user)
    db.close()

    return user


def get_token(user):
    return create_access_token(
        user_id=user.id,
        role=user.role
    )


def test_admin_can_get_dashboard(client: TestClient):
    admin = create_user(
        "admin_dashboard@woodcommerce.local",
        "ADMIN"
    )

    response = client.get(
        "/api/v1/admin/dashboard",
        headers={
            "Authorization": f"Bearer {get_token(admin)}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert "orders" in data
    assert "revenue" in data
    assert "products" in data
    assert "users" in data

    assert data["orders"]["total"] == 0
    assert data["products"]["total"] == 0
    assert data["users"]["customers"] == 0
    assert data["users"]["admins"] == 1


def test_customer_cannot_get_admin_dashboard(client: TestClient):
    customer = create_user(
        "customer_dashboard@woodcommerce.local",
        "CUSTOMER"
    )

    response = client.get(
        "/api/v1/admin/dashboard",
        headers={
            "Authorization": f"Bearer {get_token(customer)}"
        }
    )

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin access required"


def test_admin_dashboard_counts_data(client: TestClient):
    admin = create_user(
        "admin_dashboard_counts@woodcommerce.local",
        "ADMIN"
    )

    create_user(
        "customer_dashboard_counts@woodcommerce.local",
        "CUSTOMER"
    )

    db = SessionLocal()
    
    category = Category(
        name="Строительные материалы"
    )

    db.add(category)
    db.commit()
    db.refresh(category)

    product = Product(
        name="Доска 50x150",
        description="Строительная доска",
        price=1000,
        stock_quantity=5,
        unit="шт",
        category_id=category.id,
        is_active=1
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    order_new = Order(
        customer_name="Тестовый покупатель",
        status="NEW",
        total_price=5000,
        delivery_address="Москва, ул. Ленина, 1",
        user_id=admin.id
    )

    order_delivered = Order(
        customer_name="Тестовый покупатель",
        status="DELIVERED",
        total_price=12000,
        delivery_address="Москва, ул. Пушкина, 10",
        user_id=admin.id
    )

    db.add(order_new)
    db.add(order_delivered)
    db.commit()

    db.refresh(order_new)
    db.refresh(order_delivered)

    db.close()

    response = client.get(
        "/api/v1/admin/dashboard",
        headers={
            "Authorization": f"Bearer {get_token(admin)}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["orders"]["total"] == 2
    assert data["orders"]["new"] == 1
    assert data["orders"]["delivered"] == 1

    assert data["revenue"]["delivered_orders_revenue"] == 12000

    assert data["products"]["total"] == 1
    assert data["products"]["active"] == 1
    assert data["products"]["low_stock"] == 1

    assert data["users"]["customers"] == 1
    assert data["users"]["admins"] == 1


def test_admin_can_get_sales_statistics(client):
    register_response = client.post(
        "/api/v1/auth/register",
        json={
            "phone": "+79995550001",
            "password": "password123"
        }
    )

    assert register_response.status_code == 200

    # Получаем пользователя и делаем его ADMIN
    from app.database import SessionLocal
    from app.models import User

    db = SessionLocal()

    user = (
        db.query(User)
        .filter(
            User.phone == "+79995550001"
        )
        .first()
    )

    user.role = "ADMIN"

    db.commit()
    db.close()

    login_response = client.post(
        "/api/v1/auth/login",
        json={
            "phone": "+79995550001",
            "password": "password123"
        }
    )

    assert login_response.status_code == 200

    token = login_response.json()["access_token"]

    response = client.get(
        "/api/v1/admin/sales/statistics",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    data = response.json()

    assert data["total_orders"] == 0
    assert data["delivered_orders"] == 0
    assert data["cancelled_orders"] == 0
    assert data["total_revenue"] == 0
    assert data["average_order_value"] == 0
    assert data["delivery_conversion_rate"] == 0
