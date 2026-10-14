from fastapi.testclient import TestClient

from app.auth import create_access_token, hash_password
from app.database import SessionLocal
from app.models import Category, Product, User


def create_admin():
    db = SessionLocal()

    admin = User(
        email="admin_products_filters@woodcommerce.local",
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

    category_1 = Category(name="Доски")
    category_2 = Category(name="Брус")

    db.add(category_1)
    db.add(category_2)
    db.commit()

    db.refresh(category_1)
    db.refresh(category_2)

    products = [
        Product(
            name="Доска 50x100",
            description="Доска",
            price=1000,
            stock_quantity=50,
            unit="шт",
            category_id=category_1.id,
            is_active=1
        ),
        Product(
            name="Доска 50x150",
            description="Доска",
            price=2000,
            stock_quantity=5,
            unit="шт",
            category_id=category_1.id,
            is_active=1
        ),
        Product(
            name="Брус 100x100",
            description="Брус",
            price=3000,
            stock_quantity=20,
            unit="шт",
            category_id=category_2.id,
            is_active=1
        ),
        Product(
            name="Старая доска",
            description="Неактивный товар",
            price=500,
            stock_quantity=10,
            unit="шт",
            category_id=category_1.id,
            is_active=0
        )
    ]

    db.add_all(products)
    db.commit()

    for product in products:
        db.refresh(product)

    category_ids = (category_1.id, category_2.id)

    db.close()

    return category_ids


def get_admin_token(admin):
    return create_access_token(
        user_id=admin.id,
        role=admin.role
    )


def test_product_pagination(client: TestClient):
    admin = create_admin()
    create_test_data()

    token = get_admin_token(admin)

    response = client.get(
        "/api/v1/products/?limit=2&offset=0",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    products = response.json()

    assert len(products) == 2


def test_filter_products_by_category(client: TestClient):
    admin = create_admin()
    category_ids = create_test_data()

    token = get_admin_token(admin)

    response = client.get(
        f"/api/v1/products/?category_id={category_ids[0]}",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    products = response.json()

    assert len(products) == 2

    for product in products:
        assert product["category_id"] == category_ids[0]


def test_filter_products_by_active_status(client: TestClient):
    admin = create_admin()
    create_test_data()

    token = get_admin_token(admin)

    response = client.get(
        "/api/v1/products/?is_active=0",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    products = response.json()

    assert len(products) == 1
    assert products[0]["name"] == "Старая доска"
    assert products[0]["is_active"] == 0


def test_sort_products_by_price_desc(client: TestClient):
    admin = create_admin()
    create_test_data()

    token = get_admin_token(admin)

    response = client.get(
        "/api/v1/products/?sort_by=price&sort_order=desc",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    products = response.json()

    assert len(products) == 3

    prices = [product["price"] for product in products]

    assert prices == [3000, 2000, 1000]


def test_sort_products_by_name_asc(client: TestClient):
    admin = create_admin()
    create_test_data()

    token = get_admin_token(admin)

    response = client.get(
        "/api/v1/products/?sort_by=name&sort_order=asc",
        headers={
            "Authorization": f"Bearer {token}"
        }
    )

    assert response.status_code == 200

    products = response.json()

    names = [product["name"] for product in products]

    assert names == [
        "Брус 100x100",
        "Доска 50x100",
        "Доска 50x150"
    ]
