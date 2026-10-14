from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, User


def create_admin():
    db = SessionLocal()

    admin = User(
        email="admin_products_statistics@woodcommerce.local",
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
        email="customer_products_statistics@woodcommerce.local",
        password_hash=hash_password("password123"),
        role="CUSTOMER"
    )

    db.add(customer)
    db.commit()
    db.refresh(customer)
    db.close()

    return customer


def create_products():
    db = SessionLocal()

    category = Category(name="Статистика товаров")

    db.add(category)
    db.commit()
    db.refresh(category)

    products = [
        Product(
            name="Нормальный товар",
            description="Есть остаток",
            price=1000,
            stock_quantity=50,
            unit="шт",
            category_id=category.id,
            is_active=1
        ),
        Product(
            name="Товар с низким остатком",
            description="Мало товара",
            price=1500,
            stock_quantity=5,
            unit="шт",
            category_id=category.id,
            is_active=1
        ),
        Product(
            name="Товар без остатка",
            description="Нет товара",
            price=2000,
            stock_quantity=0,
            unit="шт",
            category_id=category.id,
            is_active=1
        ),
        Product(
            name="Неактивный товар",
            description="Удалённый товар",
            price=500,
            stock_quantity=100,
            unit="шт",
            category_id=category.id,
            is_active=0
        )
    ]

    db.add_all(products)
    db.commit()
    db.close()


def get_token(user):
    return create_access_token(
        user_id=user.id,
        role=user.role
    )


def test_admin_can_get_product_statistics(client: TestClient):
    admin = create_admin()
    create_products()

    token = get_token(admin)

    response = client.get(
        "/api/v1/admin/products/statistics",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    statistics = response.json()

    assert statistics["total"] == 4
    assert statistics["active"] == 3
    assert statistics["inactive"] == 1
    assert statistics["low_stock"] == 1
    assert statistics["out_of_stock"] == 1


def test_customer_cannot_get_product_statistics(client: TestClient):
    customer = create_customer()

    token = get_token(customer)

    response = client.get(
        "/api/v1/admin/products/statistics",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 403


def test_product_statistics_with_empty_database(client: TestClient):
    admin = create_admin()

    token = get_token(admin)

    response = client.get(
        "/api/v1/admin/products/statistics",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    statistics = response.json()

    assert statistics["total"] == 0
    assert statistics["active"] == 0
    assert statistics["inactive"] == 0
    assert statistics["low_stock"] == 0
    assert statistics["out_of_stock"] == 0


    
