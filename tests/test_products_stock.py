from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, User


def create_admin():
    db = SessionLocal()

    admin = User(
        email="admin_products_stock@woodcommerce.local",
        password_hash=hash_password("password123"),
        role="ADMIN"
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.close()

    return admin


def create_customer():
    db = SessionLocal()

    customer = User(
        email="customer_products_stock@woodcommerce.local",
        password_hash=hash_password("password123"),
        role="CUSTOMER"
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)
    db.close()

    return customer


def create_product():
    db = SessionLocal()

    category = Category(name="Остатки")

    db.add(category)
    db.commit()
    db.refresh(category)

    product = Product(
        name="Доска складская",
        description="Товар для проверки остатков",
        price=1500,
        stock_quantity=10,
        unit="шт",
        category_id=category.id,
        is_active=1
    )

    db.add(product)
    db.commit()
    db.refresh(product)

    product_id = product.id

    db.close()

    return product_id


def get_token(user):
    return create_access_token(
        user_id=user.id,
        role=user.role
    )


def test_admin_can_update_product_stock(client: TestClient):
    admin = create_admin()
    product_id = create_product()

    token = get_token(admin)

    response = client.patch(
        f"/api/v1/products/{product_id}/stock",
        json={
            "stock_quantity": 75
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    product = response.json()

    assert product["id"] == product_id
    assert product["stock_quantity"] == 75


def test_customer_cannot_update_product_stock(client: TestClient):
    customer = create_customer()
    product_id = create_product()

    token = get_token(customer)

    response = client.patch(
        f"/api/v1/products/{product_id}/stock",
        json={
            "stock_quantity": 75
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 403


def test_stock_cannot_be_negative(client: TestClient):
    admin = create_admin()
    product_id = create_product()

    token = get_token(admin)

    response = client.patch(
        f"/api/v1/products/{product_id}/stock",
        json={
            "stock_quantity": -10
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 422


def test_update_stock_for_missing_product(client: TestClient):
    admin = create_admin()

    token = get_token(admin)

    response = client.patch(
        "/api/v1/products/999999/stock",
        json={
            "stock_quantity": 50
        },
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 404
