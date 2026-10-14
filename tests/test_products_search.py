from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, User


def create_admin():
    db = SessionLocal()

    admin = User(
        email="admin_products_search@woodcommerce.local",
        password_hash=hash_password("password123"),
        role="ADMIN"
    )

    db.add(admin)
    db.commit()
    db.refresh(admin)
    db.close()

    return admin


def create_test_data():
    db = SessionLocal()

    category = Category(name="Пиломатериалы")

    db.add(category)
    db.commit()
    db.refresh(category)

    products = [
        Product(
            name="Доска обрезная",
            description="Сухая доска для строительства",
            price=1500,
            stock_quantity=50,
            unit="шт",
            category_id=category.id,
            is_active=1
        ),
        Product(
            name="Брус 100x100",
            description="Строительный брус",
            price=3000,
            stock_quantity=20,
            unit="шт",
            category_id=category.id,
            is_active=1
        ),
        Product(
            name="Фанера",
            description="Листовой строительный материал",
            price=2000,
            stock_quantity=30,
            unit="лист",
            category_id=category.id,
            is_active=1
        ),
        Product(
            name="Старая доска",
            description="Старая доска",
            price=500,
            stock_quantity=10,
            unit="шт",
            category_id=category.id,
            is_active=0
        )
    ]

    db.add_all(products)
    db.commit()

    db.close()


def get_admin_token(admin):
    return create_access_token(
        user_id=admin.id,
        role=admin.role
    )


def test_search_products_by_name(client: TestClient):
    admin = create_admin()
    create_test_data()

    token = get_admin_token(admin)

    response = client.get(
        "/api/v1/products/?search=доска",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    products = response.json()

    assert len(products) == 1
    assert products[0]["name"] == "Доска обрезная"


def test_search_products_by_description(client: TestClient):
    admin = create_admin()
    create_test_data()

    token = get_admin_token(admin)

    response = client.get(
        "/api/v1/products/?search=строительный",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    products = response.json()

    assert len(products) == 2


def test_search_products_combined_with_category_and_sort(client: TestClient):
    admin = create_admin()
    create_test_data()

    token = get_admin_token(admin)

    response = client.get(
        "/api/v1/products/?search=строительный&sort_by=price&sort_order=desc&limit=1",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    products = response.json()

    assert len(products) == 1
    assert products[0]["name"] == "Брус 100x100"
    assert products[0]["price"] == 3000


def test_search_does_not_return_inactive_products_by_default(client: TestClient):
    admin = create_admin()
    create_test_data()

    token = get_admin_token(admin)

    response = client.get(
        "/api/v1/products/?search=доска",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    products = response.json()

    for product in products:
        assert product["is_active"] == 1
